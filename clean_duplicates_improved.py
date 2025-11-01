import pandas as pd
import os
import re
import jieba
import unicodedata
from collections import defaultdict

# === FILE PATHS ===
file_path = "/Users/jiaqiguo/PycharmProjects/男权/result.csv"
output_dir = "/Users/jiaqiguo/PycharmProjects/男权/cleaned_output"
summary_path = os.path.join(output_dir, "summary_statistics.csv")
duplicates_log_path = os.path.join(output_dir, "duplicates_removed.txt")

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

# === ADVANCED DUPLICATE REMOVAL WITH LOGGING ===
print("🔍 检测并移除重复项...")

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

print(f"   移除了 {removed_duplicates} 条重复文本")
print(f"   发现 {len(duplicates_info)} 组不同的重复内容")

# Save duplicates log
with open(duplicates_log_path, 'w', encoding='utf-8') as f:
    f.write(f"重复项移除日志\n")
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

# === PARSE TIMESTAMP ===
df['时间'] = pd.to_datetime(
    df['发布时间'].fillna('') + ' ' + df['评论时间'].fillna('') + ' ' + df['回复时间'].fillna(''),
    errors='coerce'
)
df = df.dropna(subset=['时间'])

# === EXTRACT YEAR ===
df['年份'] = df['时间'].dt.year

# === WORD COUNTS (JIEBA) ===
print("📊 计算词数统计...")
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
print(f"📋 重复项日志: {duplicates_log_path}")
print(f"\n统计信息:")
print(f"  - 原始记录数: {before_count}")
print(f"  - 移除过短文本: {removed_short}")
print(f"  - 移除重复项: {removed_duplicates}")
print(f"  - 最终记录数: {len(df)}")
print(f"  - 总词数（清洗后）: {df['清洗后词数'].sum():,}")

# === SAMPLE OUTPUT ===
print("\n随机样本（清洗效果）:")
print("-" * 80)
sample_texts = df.sample(min(3, len(df)))
for idx, row in sample_texts.iterrows():
    print(f"\n原始文本片段: {row['原始文本'][:100]}...")
    print(f"清洗后文本片段: {row['清洗后文本'][:100]}...")
