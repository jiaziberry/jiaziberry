"""
辅助脚本：在清洗后的文件中查找剩余的重复项
用于调试和验证去重效果
"""

import pandas as pd
import os
import re
import unicodedata
from difflib import SequenceMatcher

# === CONFIGURATION ===
file_path = "/Users/jiaqiguo/PycharmProjects/男权/result.csv"
output_dir = "/Users/jiaqiguo/PycharmProjects/男权/cleaned_output"
duplicates_report = os.path.join(output_dir, "remaining_duplicates_report.txt")

# Similarity threshold for fuzzy matching (0.0 to 1.0)
SIMILARITY_THRESHOLD = 0.95

# === READ CSV ===
print("📖 读取CSV文件...")
df = pd.read_csv(file_path, encoding='utf-8')

# === COMBINE TEXT ===
df['原始文本'] = df[['正文', '评论内容', '回复内容']].fillna('').agg(' '.join, axis=1)


# === CLEANING FUNCTION (SAME AS IMPROVED SCRIPT) ===
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


# === APPLY CLEANING ===
print("🧹 清洗文本...")
df['清洗后文本'] = df['原始文本'].apply(clean_text)

# Filter out too short texts
min_length = 10
df = df[df['清洗后文本'].str.len() >= min_length]

print(f"📊 清洗后记录数: {len(df)}")


# === FIND EXACT DUPLICATES ===
print("\n🔍 查找完全重复项...")
exact_duplicates = df[df.duplicated(subset=['清洗后文本'], keep=False)]
exact_duplicate_groups = exact_duplicates.groupby('清洗后文本')

print(f"   发现 {len(exact_duplicate_groups)} 组完全重复的文本")


# === FIND FUZZY DUPLICATES (SIMILAR BUT NOT IDENTICAL) ===
print(f"\n🔍 查找相似文本（相似度 > {SIMILARITY_THRESHOLD*100}%）...")

def text_similarity(text1, text2):
    """计算两个文本的相似度 (0.0 到 1.0)"""
    return SequenceMatcher(None, text1, text2).ratio()

# Sample check for very long datasets (adjust as needed)
# For full check on large datasets, remove sampling
sample_size = min(len(df), 5000)  # Check first 5000 records
df_sample = df.head(sample_size).copy()

similar_pairs = []
texts = df_sample['清洗后文本'].tolist()
indices = df_sample.index.tolist()

print(f"   检查前 {sample_size} 条记录的相似度...")

for i in range(len(texts)):
    if i % 500 == 0:
        print(f"   进度: {i}/{len(texts)}")

    for j in range(i + 1, len(texts)):
        similarity = text_similarity(texts[i], texts[j])
        if similarity >= SIMILARITY_THRESHOLD and similarity < 1.0:
            similar_pairs.append({
                'index1': indices[i],
                'index2': indices[j],
                'similarity': similarity,
                'text1': texts[i][:200],
                'text2': texts[j][:200],
                'full_text1': texts[i],
                'full_text2': texts[j]
            })

print(f"   发现 {len(similar_pairs)} 对相似文本")


# === GENERATE REPORT ===
print(f"\n📝 生成报告...")

with open(duplicates_report, 'w', encoding='utf-8') as f:
    f.write("=" * 100 + "\n")
    f.write("重复项分析报告\n")
    f.write("=" * 100 + "\n\n")

    # === EXACT DUPLICATES SECTION ===
    f.write(f"一、完全重复项\n")
    f.write(f"-" * 100 + "\n")
    f.write(f"发现 {len(exact_duplicate_groups)} 组完全重复的文本\n\n")

    if len(exact_duplicate_groups) > 0:
        for idx, (text, group) in enumerate(exact_duplicate_groups, 1):
            f.write(f"\n重复组 #{idx}\n")
            f.write(f"重复次数: {len(group)}\n")
            f.write(f"文本长度: {len(text)} 字符\n")
            f.write(f"行索引: {group.index.tolist()}\n")
            f.write(f"\n完整文本:\n")
            f.write(f"{'-' * 100}\n")
            f.write(f"{text}\n")
            f.write(f"{'-' * 100}\n\n")

            # Show original texts for comparison
            f.write(f"原始文本对比:\n")
            for orig_idx, orig_text in group['原始文本'].items():
                f.write(f"\n  行 {orig_idx}:\n  {orig_text[:300]}...\n")
            f.write("\n" + "=" * 100 + "\n")
    else:
        f.write("✅ 未发现完全重复项！\n\n")

    # === FUZZY DUPLICATES SECTION ===
    f.write(f"\n\n二、相似文本 (相似度 >= {SIMILARITY_THRESHOLD*100}%)\n")
    f.write(f"-" * 100 + "\n")
    f.write(f"发现 {len(similar_pairs)} 对相似文本\n\n")

    if len(similar_pairs) > 0:
        for idx, pair in enumerate(similar_pairs, 1):
            f.write(f"\n相似对 #{idx}\n")
            f.write(f"相似度: {pair['similarity']*100:.2f}%\n")
            f.write(f"行索引: {pair['index1']} 和 {pair['index2']}\n")
            f.write(f"\n文本1:\n{pair['full_text1']}\n")
            f.write(f"\n文本2:\n{pair['full_text2']}\n")
            f.write(f"\n差异:\n")

            # Show character-level differences
            text1_chars = list(pair['full_text1'])
            text2_chars = list(pair['full_text2'])
            max_len = max(len(text1_chars), len(text2_chars))

            diff_positions = []
            for i in range(max_len):
                char1 = text1_chars[i] if i < len(text1_chars) else '∅'
                char2 = text2_chars[i] if i < len(text2_chars) else '∅'
                if char1 != char2:
                    diff_positions.append(f"  位置{i}: '{char1}' vs '{char2}'")

            if diff_positions:
                f.write('\n'.join(diff_positions[:20]))  # Show first 20 differences
                if len(diff_positions) > 20:
                    f.write(f"\n  ... (还有 {len(diff_positions)-20} 处差异)")

            f.write("\n" + "=" * 100 + "\n")
    else:
        f.write(f"✅ 未发现相似度 >= {SIMILARITY_THRESHOLD*100}% 的文本对！\n\n")

    # === STATISTICS SECTION ===
    f.write(f"\n\n三、统计摘要\n")
    f.write(f"-" * 100 + "\n")
    f.write(f"总记录数: {len(df)}\n")
    f.write(f"完全重复组数: {len(exact_duplicate_groups)}\n")
    f.write(f"完全重复记录数: {len(exact_duplicates)}\n")
    f.write(f"高相似度文本对数: {len(similar_pairs)}\n")
    f.write(f"检查范围: 前 {sample_size} 条记录\n")
    f.write(f"相似度阈值: {SIMILARITY_THRESHOLD*100}%\n")

print(f"\n✅ 报告已生成: {duplicates_report}")
print("\n摘要:")
print(f"  - 总记录数: {len(df)}")
print(f"  - 完全重复组: {len(exact_duplicate_groups)}")
print(f"  - 相似文本对: {len(similar_pairs)}")

# === SHOW SAMPLE ===
if len(exact_duplicate_groups) > 0:
    print("\n⚠️  发现重复项！请查看报告文件获取详情。")
    print("\n示例重复文本（前200字符）:")
    first_group = list(exact_duplicate_groups)[0]
    print(f"{first_group[0][:200]}...")
else:
    print("\n✅ 未发现完全重复项！")
