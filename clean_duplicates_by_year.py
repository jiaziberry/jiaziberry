import pandas as pd
import os
import re
import jieba
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher

# === FILE PATHS ===
file_path = "/Users/jiaqiguo/PycharmProjects/男权/result.csv"
output_dir = "/Users/jiaqiguo/PycharmProjects/男权/cleaned_output"
summary_path = os.path.join(output_dir, "summary_statistics.csv")
duplicates_log_path = os.path.join(output_dir, "duplicates_removed.txt")
fuzzy_duplicates_log_path = os.path.join(output_dir, "fuzzy_duplicates_removed.txt")

# === FUZZY DEDUPLICATION SETTINGS ===
ENABLE_FUZZY_DEDUP = True  # Set to False to disable fuzzy deduplication
SIMILARITY_THRESHOLD = 0.95  # Remove texts that are 95%+ similar
PROCESS_SPECIFIC_YEARS = []  # Leave empty to process all years, or specify like [2018, 2019, 2020]

# === SETUP ===
os.makedirs(output_dir, exist_ok=True)

# === READ CSV ===
print("📖 读取CSV文件...")
df = pd.read_csv(file_path, encoding='utf-8')
print(f"   总记录数: {len(df):,}")

# === COMBINE TEXT ===
df['原始文本'] = df[['正文', '评论内容', '回复内容']].fillna('').agg(' '.join, axis=1)


# === IMPROVED CLEANING FUNCTION ===
def clean_text(text):
    if pd.isna(text):
        return ''

    text = str(text)
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'引用.*?(说|回复|的话)?[:：]\s*".*?"', '', text, flags=re.DOTALL)
    text = re.sub(r'(引用\s*(@?[\u4e00-\u9fa5a-zA-Z0-9_]+)\s*[:：])\s*".*?"', '', text, flags=re.DOTALL)
    text = re.sub(r'引用.*?[。！？]', '', text)
    text = re.sub(r'(@\w+)|（.*?）|\[.*?\]|用户.*?说：', '', text)
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', text)
    return text


def text_similarity(text1, text2):
    """计算两个文本的相似度 (0.0 到 1.0)"""
    return SequenceMatcher(None, text1, text2).ratio()


def fuzzy_deduplicate_dataframe(df_subset, year_label):
    """对数据框子集进行模糊去重"""
    print(f"\n{'='*80}")
    print(f"🔍 处理 {year_label}")
    print(f"{'='*80}")

    fuzzy_duplicates_info = []
    before_fuzzy = len(df_subset)

    # Reset index for easier tracking
    df_subset = df_subset.reset_index(drop=True)

    indices_to_remove = set()
    texts = df_subset['清洗后文本'].tolist()

    print(f"   记录数: {len(texts):,}")
    print(f"   预估比较次数: {(len(texts) * (len(texts) - 1)) // 2:,}")

    # Progress tracking
    total_comparisons = (len(texts) * (len(texts) - 1)) // 2
    comparisons_done = 0
    last_progress = 0

    for i in range(len(texts)):
        if i in indices_to_remove:
            continue

        for j in range(i + 1, len(texts)):
            if j in indices_to_remove:
                continue

            comparisons_done += 1

            # Progress update every 1%
            current_progress = int((comparisons_done / total_comparisons) * 100)
            if current_progress > last_progress and current_progress % 5 == 0:
                print(f"   进度: {current_progress}% ({comparisons_done:,}/{total_comparisons:,} 比较)")
                last_progress = current_progress

            similarity = text_similarity(texts[i], texts[j])

            if similarity >= SIMILARITY_THRESHOLD:
                indices_to_remove.add(j)

                fuzzy_duplicates_info.append({
                    'year': year_label,
                    'kept_index': i,
                    'removed_index': j,
                    'similarity': similarity,
                    'kept_text': texts[i],
                    'removed_text': texts[j]
                })

    # Remove fuzzy duplicates
    df_result = df_subset[~df_subset.index.isin(indices_to_remove)]
    removed_fuzzy = before_fuzzy - len(df_result)

    print(f"   ✅ {year_label} 完成!")
    print(f"   移除了 {removed_fuzzy:,} 条高相似度文本")
    print(f"   剩余 {len(df_result):,} 条记录")

    return df_result, fuzzy_duplicates_info


# === APPLY CLEANING ===
print("\n🧹 清洗文本中...")
df['清洗后文本'] = df['原始文本'].apply(clean_text)

# === REMOVE EMPTY OR TOO SHORT TEXTS ===
print("\n🗑️  移除空白或过短文本...")
min_length = 10
before_count = len(df)
df = df[df['清洗后文本'].str.len() >= min_length]
removed_short = before_count - len(df)
print(f"   移除了 {removed_short:,} 条过短文本")

# === PARSE TIMESTAMP FIRST (so we can group by year) ===
print("\n📅 解析时间戳...")
df['时间'] = pd.to_datetime(
    df['发布时间'].fillna('') + ' ' + df['评论时间'].fillna('') + ' ' + df['回复时间'].fillna(''),
    errors='coerce'
)
df = df.dropna(subset=['时间'])
df['年份'] = df['时间'].dt.year

# Show year distribution
year_counts = df['年份'].value_counts().sort_index()
print(f"\n📊 按年份分布:")
for year, count in year_counts.items():
    print(f"   {year}: {count:,} 条记录")

# === EXACT DUPLICATE REMOVAL WITH LOGGING ===
print("\n🔍 步骤1: 检测并移除完全重复项（全部数据）...")

duplicates_info = defaultdict(list)
before_dedup = len(df)

duplicate_mask = df.duplicated(subset=['清洗后文本'], keep='first')
duplicate_texts = df[duplicate_mask]['清洗后文本'].values

for dup_text in duplicate_texts:
    duplicates_info[dup_text[:100] + '...'].append(dup_text)

df = df[~duplicate_mask]
removed_duplicates = before_dedup - len(df)

print(f"   移除了 {removed_duplicates:,} 条完全重复文本")
print(f"   发现 {len(duplicates_info):,} 组不同的重复内容")

# Save exact duplicates log
with open(duplicates_log_path, 'w', encoding='utf-8') as f:
    f.write(f"完全重复项移除日志\n")
    f.write(f"=" * 80 + "\n")
    f.write(f"总共移除: {removed_duplicates} 条重复记录\n")
    f.write(f"涉及: {len(duplicates_info)} 组不同文本\n\n")

    for idx, (preview, texts) in enumerate(duplicates_info.items(), 1):
        f.write(f"\n重复组 #{idx} (共 {len(texts)} 条重复)\n")
        f.write(f"-" * 80 + "\n")
        f.write(f"文本预览: {preview}\n")
        if len(texts) > 0:
            f.write(f"完整文本:\n{texts[0]}\n")

print(f"   详细日志已保存到: {duplicates_log_path}")

# === FUZZY DUPLICATE REMOVAL BY YEAR ===
if ENABLE_FUZZY_DEDUP:
    print("\n" + "=" * 80)
    print("🔍 步骤2: 按年份检测并移除高相似度文本")
    print(f"   相似度阈值: {SIMILARITY_THRESHOLD*100}%")
    print("=" * 80)

    all_fuzzy_duplicates_info = []
    processed_dfs = []

    # Get years to process
    years = sorted(df['年份'].unique())
    if PROCESS_SPECIFIC_YEARS:
        years = [y for y in years if y in PROCESS_SPECIFIC_YEARS]
        print(f"\n⚠️  只处理指定年份: {PROCESS_SPECIFIC_YEARS}")

    total_before_fuzzy = len(df)

    # Process each year separately
    for year in years:
        year_df = df[df['年份'] == year].copy()

        # Perform fuzzy deduplication on this year
        deduplicated_df, fuzzy_info = fuzzy_deduplicate_dataframe(year_df, f"{year}年")

        processed_dfs.append(deduplicated_df)
        all_fuzzy_duplicates_info.extend(fuzzy_info)

    # Combine all years back together
    df = pd.concat(processed_dfs, ignore_index=True)

    total_removed_fuzzy = total_before_fuzzy - len(df)

    print("\n" + "=" * 80)
    print(f"✅ 模糊去重完成!")
    print(f"   总共移除: {total_removed_fuzzy:,} 条高相似度文本")
    print(f"   发现: {len(all_fuzzy_duplicates_info):,} 对相似文本")
    print("=" * 80)

    # Save fuzzy duplicates log
    print(f"\n💾 保存模糊重复日志...")
    with open(fuzzy_duplicates_log_path, 'w', encoding='utf-8') as f:
        f.write(f"高相似度文本移除日志（按年份处理）\n")
        f.write(f"=" * 80 + "\n")
        f.write(f"相似度阈值: {SIMILARITY_THRESHOLD*100}%\n")
        f.write(f"总共移除: {total_removed_fuzzy} 条相似记录\n")
        f.write(f"涉及: {len(all_fuzzy_duplicates_info)} 对相似文本\n\n")

        # Group by year for the log
        by_year = defaultdict(list)
        for info in all_fuzzy_duplicates_info:
            by_year[info['year']].append(info)

        for year in sorted(by_year.keys()):
            f.write(f"\n{'='*80}\n")
            f.write(f"{year} - {len(by_year[year])} 对相似文本\n")
            f.write(f"{'='*80}\n\n")

            for idx, info in enumerate(by_year[year], 1):
                f.write(f"\n{year} 相似对 #{idx}\n")
                f.write(f"-" * 80 + "\n")
                f.write(f"相似度: {info['similarity']*100:.2f}%\n")
                f.write(f"保留索引: {info['kept_index']}\n")
                f.write(f"移除索引: {info['removed_index']}\n")
                f.write(f"\n保留文本:\n{info['kept_text']}\n")
                f.write(f"\n移除文本:\n{info['removed_text']}\n")
                f.write(f"\n" + "=" * 80 + "\n")

    print(f"   详细日志已保存到: {fuzzy_duplicates_log_path}")

# === WORD COUNTS (JIEBA) ===
print("\n📊 计算词数统计...")
df['原始词数'] = df['原始文本'].apply(lambda text: len(list(jieba.cut(text))) if isinstance(text, str) else 0)
df['清洗后词数'] = df['清洗后文本'].apply(lambda text: len(list(jieba.cut(text))) if isinstance(text, str) else 0)

# === GENERATE CLEAN TEXTS AND SUMMARY ===
print("\n💾 生成输出文件...")
summary = []

for year, group in df.groupby('年份'):
    year_text = '\n\n'.join(group['清洗后文本'].dropna().astype(str).tolist())
    year_path = os.path.join(output_dir, f'cleaned_{year}.txt')
    with open(year_path, 'w', encoding='utf-8') as f:
        f.write(year_text)

    summary.append({
        '年份': year,
        '原始词数': group['原始词数'].sum(),
        '清洗后词数': group['清洗后词数'].sum(),
        '帖子数': group['帖子ID'].nunique() if '帖子ID' in group.columns else 'N/A',
        '记录数': len(group)
    })

# === TOTAL SUMMARY ROW ===
summary_df = pd.DataFrame(summary)
total_row = {
    '年份': '总计',
    '原始词数': df['原始词数'].sum(),
    '清洗后词数': df['清洗后词数'].sum(),
    '帖子数': df['帖子ID'].nunique() if '帖子ID' in df.columns else 'N/A',
    '记录数': len(df)
}
summary_df = pd.concat([summary_df, pd.DataFrame([total_row])])

# === SAVE SUMMARY CSV ===
summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')

# === FINAL VERIFICATION ===
print("\n" + "=" * 80)
print("✅ 全部处理完成！")
print("=" * 80)
print(f"📁 输出目录: {output_dir}")
print(f"📊 统计摘要: {summary_path}")
print(f"📋 完全重复项日志: {duplicates_log_path}")
if ENABLE_FUZZY_DEDUP:
    print(f"📋 高相似度文本日志: {fuzzy_duplicates_log_path}")
print(f"\n统计信息:")
print(f"  - 原始记录数: {before_count:,}")
print(f"  - 移除过短文本: {removed_short:,}")
print(f"  - 移除完全重复: {removed_duplicates:,}")
if ENABLE_FUZZY_DEDUP:
    print(f"  - 移除高相似度: {total_removed_fuzzy:,}")
print(f"  - 最终记录数: {len(df):,}")
print(f"  - 总词数（清洗后）: {df['清洗后词数'].sum():,}")

print("\n🎉 完成！")
