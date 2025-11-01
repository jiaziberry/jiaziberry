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
SIMILARITY_THRESHOLD = 0.95  # Remove texts that are 95%+ similar (adjust as needed: 0.9, 0.95, 0.98, etc.)
FUZZY_BATCH_SIZE = 1000  # Process in batches to avoid memory issues

# === SETUP ===
os.makedirs(output_dir, exist_ok=True)

# === READ CSV ===
df = pd.read_csv(file_path, encoding='utf-8')

# === COMBINE TEXT ===
df['原始文本'] = df[['正文', '评论内容', '回复内容']].fillna('').agg(' '.join, axis=1)


# === IMPROVED CLEANING FUNCTION ===
def clean_text(text):
    if pd.isna(text):
        return ''

    # Convert to string if not already
    text = str(text)

    # Unicode normalization (NFKC - compatibility composition)
    # This handles different Unicode representations of the same character
    text = unicodedata.normalize('NFKC', text)

    # Remove quoted blocks: "引用 XX 说：..." or "引用 @XXX：..." style
    text = re.sub(r'引用.*?(说|回复|的话)?[:：]\s*".*?"', '', text, flags=re.DOTALL)
    text = re.sub(r'(引用\s*(@?[\u4e00-\u9fa5a-zA-Z0-9_]+)\s*[:：])\s*".*?"', '', text, flags=re.DOTALL)
    text = re.sub(r'引用.*?[。！？]', '', text)

    # Remove metadata: @mentions, brackets, "用户XXX说：" patterns
    text = re.sub(r'(@\w+)|（.*?）|\[.*?\]|用户.*?说：', '', text)

    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

    # Normalize whitespace aggressively
    # Replace all whitespace characters (space, tab, newline, etc.) with single space
    text = re.sub(r'\s+', ' ', text)

    # Remove leading/trailing whitespace
    text = text.strip()

    # Remove zero-width characters and other invisible characters
    text = re.sub(r'[\u200b-\u200f\u202a-\u202e\ufeff]', '', text)

    return text


def text_similarity(text1, text2):
    """计算两个文本的相似度 (0.0 到 1.0)"""
    return SequenceMatcher(None, text1, text2).ratio()


# === APPLY CLEANING ===
print("🧹 清洗文本中...")
df['清洗后文本'] = df['原始文本'].apply(clean_text)

# === REMOVE EMPTY OR TOO SHORT TEXTS ===
print("🗑️  移除空白或过短文本...")
min_length = 10  # Minimum character length after cleaning
before_count = len(df)
df = df[df['清洗后文本'].str.len() >= min_length]
removed_short = before_count - len(df)
print(f"   移除了 {removed_short} 条过短文本（少于{min_length}字符）")

# === EXACT DUPLICATE REMOVAL WITH LOGGING ===
print("🔍 步骤1: 检测并移除完全重复项...")

# Track duplicates for logging
duplicates_info = defaultdict(list)
before_dedup = len(df)

# Find duplicates
duplicate_mask = df.duplicated(subset=['清洗后文本'], keep='first')
duplicate_texts = df[duplicate_mask]['清洗后文本'].values

# Log duplicate information
for dup_text in duplicate_texts:
    duplicates_info[dup_text[:100] + '...'].append(dup_text)

# Remove duplicates
df = df[~duplicate_mask]
removed_duplicates = before_dedup - len(df)

print(f"   移除了 {removed_duplicates} 条完全重复文本")
print(f"   发现 {len(duplicates_info)} 组不同的重复内容")

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

# === FUZZY DUPLICATE REMOVAL (OPTIONAL) ===
if ENABLE_FUZZY_DEDUP:
    print(f"\n🔍 步骤2: 检测并移除高相似度文本（阈值: {SIMILARITY_THRESHOLD*100}%）...")

    fuzzy_duplicates_info = []
    before_fuzzy = len(df)

    # Reset index for easier tracking
    df = df.reset_index(drop=True)

    # Process in batches to manage memory
    total_records = len(df)
    indices_to_remove = set()

    print(f"   总记录数: {total_records}")
    print(f"   批次大小: {FUZZY_BATCH_SIZE}")

    # Compare each text with all subsequent texts
    texts = df['清洗后文本'].tolist()

    for i in range(len(texts)):
        if i in indices_to_remove:
            continue

        if i % 100 == 0:
            print(f"   进度: {i}/{len(texts)} ({i/len(texts)*100:.1f}%)")

        for j in range(i + 1, len(texts)):
            if j in indices_to_remove:
                continue

            # Only compare if not already marked for removal
            similarity = text_similarity(texts[i], texts[j])

            if similarity >= SIMILARITY_THRESHOLD:
                # Mark j for removal (keep i, remove j)
                indices_to_remove.add(j)

                # Log this fuzzy duplicate
                fuzzy_duplicates_info.append({
                    'kept_index': i,
                    'removed_index': j,
                    'similarity': similarity,
                    'kept_text': texts[i],
                    'removed_text': texts[j]
                })

    # Remove fuzzy duplicates
    df = df[~df.index.isin(indices_to_remove)]
    removed_fuzzy = before_fuzzy - len(df)

    print(f"   移除了 {removed_fuzzy} 条高相似度文本")
    print(f"   发现 {len(fuzzy_duplicates_info)} 对相似文本")

    # Save fuzzy duplicates log
    with open(fuzzy_duplicates_log_path, 'w', encoding='utf-8') as f:
        f.write(f"高相似度文本移除日志\n")
        f.write(f"=" * 80 + "\n")
        f.write(f"相似度阈值: {SIMILARITY_THRESHOLD*100}%\n")
        f.write(f"总共移除: {removed_fuzzy} 条相似记录\n")
        f.write(f"涉及: {len(fuzzy_duplicates_info)} 对相似文本\n\n")

        for idx, info in enumerate(fuzzy_duplicates_info, 1):
            f.write(f"\n相似对 #{idx}\n")
            f.write(f"-" * 80 + "\n")
            f.write(f"相似度: {info['similarity']*100:.2f}%\n")
            f.write(f"保留索引: {info['kept_index']}\n")
            f.write(f"移除索引: {info['removed_index']}\n")
            f.write(f"\n保留文本:\n{info['kept_text']}\n")
            f.write(f"\n移除文本:\n{info['removed_text']}\n")
            f.write(f"\n" + "=" * 80 + "\n")

    print(f"   详细日志已保存到: {fuzzy_duplicates_log_path}")

# === PARSE TIMESTAMP ===
df['时间'] = pd.to_datetime(
    df['发布时间'].fillna('') + ' ' + df['评论时间'].fillna('') + ' ' + df['回复时间'].fillna(''),
    errors='coerce'
)
df = df.dropna(subset=['时间'])

# === EXTRACT YEAR ===
df['年份'] = df['时间'].dt.year

# === WORD COUNTS (JIEBA) ===
print("\n📊 计算词数统计...")
df['原始词数'] = df['原始文本'].apply(lambda text: len(list(jieba.cut(text))) if isinstance(text, str) else 0)
df['清洗后词数'] = df['清洗后文本'].apply(lambda text: len(list(jieba.cut(text))) if isinstance(text, str) else 0)

# === GENERATE CLEAN TEXTS AND SUMMARY ===
print("💾 生成输出文件...")
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
print("✅ 处理完成！")
print("=" * 80)
print(f"📁 输出目录: {output_dir}")
print(f"📊 统计摘要: {summary_path}")
print(f"📋 完全重复项日志: {duplicates_log_path}")
if ENABLE_FUZZY_DEDUP:
    print(f"📋 高相似度文本日志: {fuzzy_duplicates_log_path}")
print(f"\n统计信息:")
print(f"  - 原始记录数: {before_count}")
print(f"  - 移除过短文本: {removed_short}")
print(f"  - 移除完全重复: {removed_duplicates}")
if ENABLE_FUZZY_DEDUP:
    print(f"  - 移除高相似度: {removed_fuzzy}")
print(f"  - 最终记录数: {len(df)}")
print(f"  - 总词数（清洗后）: {df['清洗后词数'].sum():,}")

# === SAMPLE OUTPUT ===
print("\n随机样本（清洗效果）:")
print("-" * 80)
sample_texts = df.sample(min(3, len(df)))
for idx, row in sample_texts.iterrows():
    print(f"\n原始文本片段: {row['原始文本'][:100]}...")
    print(f"清洗后文本片段: {row['清洗后文本'][:100]}...")
