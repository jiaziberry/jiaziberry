import os
import re
import pandas as pd
from ltp import LTP
from collections import defaultdict

# === PATH CONFIG ===
input_dir = "/Users/jiaqiguo/PycharmProjects/男权/cleaned_output"
output_csv = os.path.join(input_dir, "metaphor_extracted_permissive.csv")
rejected_csv = os.path.join(input_dir, "metaphor_rejected_log.csv")

# === CONFIGURATION FLAGS ===
USE_STRICT_SEMANTIC_FILTER = False  # Set to True for old behavior
LOG_REJECTIONS = True  # Log rejected metaphors for review
MIN_TENOR_LENGTH = 2
MIN_VEHICLE_LENGTH = 2

# === INIT LTP ===
ltp = LTP()

# === COMPARATOR LISTS ===
# EXPLICIT metaphor markers ONLY - no "是" as single comparator
COMPARATORS_SINGLE = {
    "像", "如同", "仿佛", "好比", "就像", "就象", "好像",
    "恰似", "犹如", "宛如", "若", "似", "类似",
    "象", "好象"  # Added variants
}

# Double-word patterns (definitely metaphorical)
COMPARATORS_DOUBLE = [
    ("和", "一样"), ("和", "类似"), ("和", "相似"),
    ("跟", "一样"), ("跟", "类似"), ("跟", "相似"),
    ("与", "一样"), ("与", "类似"), ("与", "相似"),
    ("像", "一样"), ("像", "那样"), ("像", "似的"),
    ("如", "一般"), ("似", "的"), ("和", "似的"),
    ("跟", "似的"), ("同", "一样")
]

# Triple-word patterns (keep emphatic "是" patterns)
COMPARATORS_TRIPLE = [
    ("就", "和", "一样"), ("就", "跟", "一样"),
    ("就", "像", "一样"),
    ("简直", "就", "是"),  # Keep: emphatic pattern
    ("简直", "就", "像"),
    ("简直", "像", "是")  # Keep: emphatic pattern
]

# MINIMAL non-metaphor list - only truly generic terms
NON_METAPHOR_TERMS = {
    "东西", "事情", "时候", "地方", "那个", "这个", "什么", "怎么"
}


# === SEMANTIC CATEGORIES (OPTIONAL) ===
def get_semantic_category(word):
    """
    Categorize words by semantic type.
    This is now OPTIONAL and only used if USE_STRICT_SEMANTIC_FILTER = True
    """
    concrete_objects = {
        '牛', '马', '狗', '猪', '羊', '驴', '鸡', '鸟', '鱼', '虫', '兽',
        '树', '花', '草', '叶', '根', '枝', '果',
        '山', '石', '水', '河', '海', '云', '雨', '雪', '风',
        '刀', '剑', '枪', '箭', '盾', '工具', '武器',
        '垃圾', '毒药', '寄生虫', '棉袄', '出气筒',
        '天使', '恶魔', '鬼', '怪物'
    }

    abstract_concepts = {
        '爱', '恨', '情', '心', '思', '想', '念', '梦',
        '希望', '理想', '信念', '价值', '自由', '平等', '权利',
        '快乐', '痛苦', '悲伤', '幸福', '怜惜', '怜悯', '同情',
        '迷恋', '爱情', '友情', '亲情'
    }

    human_related = {
        '人', '男', '女', '孩', '儿', '童', '子', '妇', '夫', '妻',
        '父', '母', '亲', '师', '生', '友'
    }

    # Check full word and characters
    if word in concrete_objects or any(c in concrete_objects for c in word):
        return 'CONCRETE'
    if word in abstract_concepts or any(c in abstract_concepts for c in word):
        return 'ABSTRACT'
    if word in human_related or any(c in human_related for c in word):
        return 'HUMAN'

    return 'OTHER'


# === COMPLETE NOUN PHRASE CHECK ===
def is_complete_noun_phrase(words, poses, start_idx, end_idx):
    """Check if vehicle is a complete noun phrase (not just attributive clause)"""
    if end_idx >= len(words):
        return False

    # Check if ends with 的 without noun following
    if start_idx < len(words) and words[end_idx - 1] == '的':
        if end_idx >= len(words):
            return False
        if end_idx < len(poses) and poses[end_idx].startswith('n'):
            return False  # Stopped too early, noun follows

    # Must contain at least one noun
    has_noun = any(poses[i].startswith('n') for i in range(start_idx, end_idx) if i < len(poses))
    if not has_noun:
        return False

    # Last content word should be noun/pronoun
    last_content_pos = None
    for i in range(end_idx - 1, start_idx - 1, -1):
        if i < len(words) and words[i] not in ('的', '地', '得', '，'):
            last_content_pos = poses[i] if i < len(poses) else None
            break

    if last_content_pos and not (last_content_pos.startswith('n') or last_content_pos == 'r'):
        return False

    return True


# === VEHICLE EXTRACTION ===
def extract_vehicle_safe(words, poses, start_idx, max_length=12):
    """
    Extract vehicle with proper 的-handling.
    Must extract complete noun phrase, not just attributive modifiers.
    """
    vehicle_parts = []
    vehicle_indices = []
    has_de = False

    i = start_idx
    while i < min(len(words), start_idx + max_length):
        word = words[i]
        pos = poses[i] if i < len(poses) else ''

        # Track 的 - must get noun after it
        if word == '的':
            has_de = True
            vehicle_parts.append(word)
            vehicle_indices.append(i)
            i += 1
            continue

        # If we saw 的, must get the noun
        if has_de and pos.startswith('n'):
            vehicle_parts.append(word)
            vehicle_indices.append(i)
            has_de = False
            i += 1
            continue

        # Regular extraction
        if (pos.startswith('n') or pos.startswith('a') or
                pos.startswith('v') or pos in ('m', 'q') or
                word in ('地', '得')):
            vehicle_parts.append(word)
            vehicle_indices.append(i)
            i += 1
        # Stop conditions
        elif pos == 'wp' or word in ('，', '。', '！', '？', '；', '、'):
            break
        elif pos == 'c' and len(vehicle_parts) >= 2:
            break
        else:
            if len(vehicle_parts) >= 2:
                break
            i += 1

    # CRITICAL: Can't end with 的
    if vehicle_parts and vehicle_parts[-1] == '的':
        return None, []

    vehicle = ''.join(vehicle_parts).strip()
    vehicle = re.sub(r'^[的地得]+', '', vehicle)

    # Must have noun
    has_noun = any(poses[idx].startswith('n') for idx in vehicle_indices if idx < len(poses))
    if not has_noun:
        return None, []

    return vehicle, vehicle_indices


# === TENOR EXTRACTION ===
def extract_tenor_safe(words, poses, end_idx, max_length=8):
    """Extract tenor going backwards from comparator"""
    tenor_parts = []
    tenor_indices = []

    for j in range(end_idx - 1, max(end_idx - max_length - 1, -1), -1):
        word = words[j]
        pos = poses[j] if j < len(poses) else ''

        # Core nouns and pronouns
        if pos.startswith('n') or pos == 'r':
            tenor_parts.insert(0, word)
            tenor_indices.insert(0, j)
        # Modifiers
        elif (pos.startswith('a') or word in ('的', '之', '这', '那', '此', '该') or
              pos in ('m', 'q')) and len(tenor_parts) > 0:
            tenor_parts.insert(0, word)
            tenor_indices.insert(0, j)
        # Stop at verbs/punctuation
        elif pos.startswith('v') or pos == 'wp' or word in ('，', '。'):
            break
        else:
            if len(tenor_parts) >= 1:
                break

    tenor = ''.join(tenor_parts).strip()
    tenor = re.sub(r'^[的之]+', '', tenor)

    # Must have noun
    has_noun = any(poses[idx].startswith('n') or poses[idx] == 'r'
                   for idx in tenor_indices if idx < len(poses))
    if not has_noun:
        return None, []

    return tenor, tenor_indices


# === CONTEXT EXTRACTION ===
def extract_context(words, poses, vehicle_end, max_length=15):
    """Extract context explaining the comparison"""
    context_parts = []

    for i in range(vehicle_end, min(len(words), vehicle_end + max_length)):
        word = words[i]
        pos = poses[i] if i < len(poses) else ''

        # Stop at sentence endings
        if word in ('。', '！', '？', '；'):
            break

        # Include descriptive content
        if (pos.startswith('v') or pos.startswith('a') or pos.startswith('d') or
                pos in ('m', 'q', 'c') or word in ('的', '地', '得', '着', '了', '过', '，')):
            context_parts.append(word)

    context = ''.join(context_parts).strip()
    context = re.sub(r'^[，、的地得]+|[，、的地得]+$', '', context)

    return context if len(context) >= 2 else None


# === VALIDATION (PERMISSIVE VERSION) ===
def is_valid_metaphor(tenor, vehicle, context, words, poses, tenor_indices, vehicle_indices):
    """
    Validate metaphors with PERMISSIVE filtering.
    Since we use explicit markers, trust them unless there's clear reason not to.
    """

    # Basic checks
    if not tenor or not vehicle:
        return False, "Missing tenor or vehicle"

    if len(tenor) < MIN_TENOR_LENGTH or len(vehicle) < MIN_VEHICLE_LENGTH:
        return False, f"Too short (tenor:{len(tenor)}, vehicle:{len(vehicle)})"

    # Check complete noun phrase (keep this - important structural check)
    if vehicle_indices:
        start_idx = vehicle_indices[0]
        end_idx = vehicle_indices[-1] + 1
        if not is_complete_noun_phrase(words, poses, start_idx, end_idx):
            return False, "Incomplete noun phrase (attributive clause only)"

    # Identical check
    if tenor == vehicle:
        return False, "Identical tenor and vehicle"

    # Temporal/numeric filter (keep this - these are literal comparisons)
    if (re.match(r'^[\d年月日时分秒]+$', tenor) or
            re.match(r'^[\d年月日时分秒]+$', vehicle)):
        return False, "Temporal/numeric comparison (literal)"

    # Both are truly generic terms (MINIMAL list now)
    if tenor in NON_METAPHOR_TERMS and vehicle in NON_METAPHOR_TERMS:
        return False, "Both generic literal terms"

    # === OPTIONAL STRICT SEMANTIC FILTER ===
    if USE_STRICT_SEMANTIC_FILTER:
        tenor_cat = get_semantic_category(tenor)
        vehicle_cat = get_semantic_category(vehicle)

        # In strict mode, reject same human category
        if tenor_cat == vehicle_cat and tenor_cat == 'HUMAN':
            return False, "Same human category (literal) [STRICT MODE]"

    # === PERMISSIVE MODE ===
    # If we have an explicit comparator (像, 如同, etc.), trust it!
    return True, "Valid - explicit metaphor marker"


# === MAIN EXTRACTION ===
def extract_metaphors(text):
    """
    Extract metaphors using ONLY explicit markers.
    No ambiguous "是" as single comparator.
    """
    if not text or not isinstance(text, str) or not re.search(r'[\u4e00-\u9fff]', text):
        return []

    results = []

    try:
        result = ltp.pipeline([text], tasks=["cws", "pos", "dep"], return_dict=True)
        words = result["cws"][0]
        poses = result["pos"][0]
        deps = result["dep"][0]

        i = 0
        while i < len(words):
            word = words[i]
            metaphor_found = False

            # === THREE-WORD PATTERNS ===
            if i + 3 < len(words):
                for w1, w2, w3 in COMPARATORS_TRIPLE:
                    if (words[i] == w1 and words[i + 1] == w2):
                        w3_pos = None
                        for j in range(i + 2, min(i + 8, len(words))):
                            if words[j] == w3:
                                w3_pos = j
                                break

                        if w3_pos is not None:
                            tenor, tenor_idx = extract_tenor_safe(words, poses, i)
                            vehicle, vehicle_idx = extract_vehicle_safe(words, poses, w3_pos + 1)

                            if tenor and vehicle and vehicle_idx:
                                comparator = f"{w1}{w2}...{w3}"
                                vehicle_end = vehicle_idx[-1] + 1
                                context = extract_context(words, poses, vehicle_end)

                                is_valid, reason = is_valid_metaphor(
                                    tenor, vehicle, context, words, poses,
                                    tenor_idx, vehicle_idx
                                )

                                if is_valid:
                                    results.append({
                                        'tenor': tenor,
                                        'comparator': comparator,
                                        'vehicle': vehicle,
                                        'context': context,
                                        'pattern': '3-word',
                                        'confidence': 'high',
                                        'validation': reason
                                    })
                                    metaphor_found = True
                                    i = w3_pos + 1
                                    break

            if metaphor_found:
                i += 1
                continue

            # === DOUBLE-WORD PATTERNS ===
            if i + 2 < len(words):
                for w1, w2 in COMPARATORS_DOUBLE:
                    if words[i] == w1:
                        w2_pos = None
                        for offset in range(1, min(10, len(words) - i)):
                            if words[i + offset] == w2:
                                w2_pos = i + offset
                                break

                        if w2_pos is not None:
                            tenor, tenor_idx = extract_tenor_safe(words, poses, i)
                            vehicle, vehicle_idx = extract_vehicle_safe(words, poses, i + 1)

                            if tenor and vehicle and vehicle_idx:
                                # Remove w2 from vehicle
                                vehicle = vehicle.replace(w2, '').strip()
                                vehicle = re.sub(r'^[的]+|[的]+$', '', vehicle)

                                if len(vehicle) >= MIN_VEHICLE_LENGTH:
                                    comparator = f"{w1}...{w2}"
                                    vehicle_end = vehicle_idx[-1] + 1
                                    context = extract_context(words, poses, vehicle_end)

                                    is_valid, reason = is_valid_metaphor(
                                        tenor, vehicle, context, words, poses,
                                        tenor_idx, vehicle_idx
                                    )

                                    if is_valid:
                                        results.append({
                                            'tenor': tenor,
                                            'comparator': comparator,
                                            'vehicle': vehicle,
                                            'context': context,
                                            'pattern': '2-word',
                                            'confidence': 'high',
                                            'validation': reason
                                        })
                                        metaphor_found = True
                                        i = w2_pos + 1
                                        break

            if metaphor_found:
                i += 1
                continue

            # === SINGLE-WORD COMPARATORS (NO "是"!) ===
            if word in COMPARATORS_SINGLE:
                if 0 < i < len(words) - 1:
                    tenor, tenor_idx = extract_tenor_safe(words, poses, i)
                    vehicle, vehicle_idx = extract_vehicle_safe(words, poses, i + 1)

                    if tenor and vehicle and vehicle_idx:
                        comparator = word
                        vehicle_end = vehicle_idx[-1] + 1
                        context = extract_context(words, poses, vehicle_end)

                        is_valid, reason = is_valid_metaphor(
                            tenor, vehicle, context, words, poses,
                            tenor_idx, vehicle_idx
                        )

                        if is_valid:
                            results.append({
                                'tenor': tenor,
                                'comparator': comparator,
                                'vehicle': vehicle,
                                'context': context,
                                'pattern': '1-word',
                                'confidence': 'high',
                                'validation': reason
                            })

            i += 1

    except Exception as e:
        print(f"❌ Error: {text[:50]} → {str(e)}")

    return results


# === REJECTION LOGGING VERSION ===
def extract_metaphors_with_logging(text, year, filename, line_num):
    """
    Extract metaphors AND log rejections for review.
    """
    if not text or not isinstance(text, str) or not re.search(r'[\u4e00-\u9fff]', text):
        return [], []

    accepted = []
    rejected = []

    try:
        result = ltp.pipeline([text], tasks=["cws", "pos", "dep"], return_dict=True)
        words = result["cws"][0]
        poses = result["pos"][0]
        deps = result["dep"][0]

        i = 0
        while i < len(words):
            word = words[i]
            metaphor_found = False

            # Process all patterns same as before, but log rejections
            # I'll implement the single-word pattern as example

            # === SINGLE-WORD COMPARATORS ===
            if word in COMPARATORS_SINGLE:
                if 0 < i < len(words) - 1:
                    tenor, tenor_idx = extract_tenor_safe(words, poses, i)
                    vehicle, vehicle_idx = extract_vehicle_safe(words, poses, i + 1)

                    if tenor and vehicle and vehicle_idx:
                        comparator = word
                        vehicle_end = vehicle_idx[-1] + 1
                        context = extract_context(words, poses, vehicle_end)

                        is_valid, reason = is_valid_metaphor(
                            tenor, vehicle, context, words, poses,
                            tenor_idx, vehicle_idx
                        )

                        metaphor_data = {
                            'tenor': tenor,
                            'comparator': comparator,
                            'vehicle': vehicle,
                            'context': context,
                            'pattern': '1-word',
                            'confidence': 'high',
                            'validation': reason
                        }

                        if is_valid:
                            accepted.append(metaphor_data)
                        elif LOG_REJECTIONS:
                            rejected.append({
                                **metaphor_data,
                                'year': year,
                                'filename': filename,
                                'line_num': line_num,
                                'original_text': text,
                                'rejection_reason': reason
                            })

            i += 1

    except Exception as e:
        print(f"❌ Error: {text[:50]} → {str(e)}")

    return accepted, rejected


# === MAIN LOOP ===
all_results = []
all_rejected = []
stats = defaultdict(int)
rejection_reasons = defaultdict(int)

print("=" * 80)
print("🔍 提取比喻 - PERMISSIVE MODE")
print("=" * 80)
print(f"✓ 包含明确比喻标记词: 像, 犹如, 如同, 仿佛, 好比, 象, 和...一样, 简直就是 等")
print(f"✓ 排除单独的'是'作为比喻词")
print(f"✓ 语义过滤: {'严格模式 (OLD)' if USE_STRICT_SEMANTIC_FILTER else '宽松模式 (NEW)'}")
print(f"✓ 拒绝日志: {'启用' if LOG_REJECTIONS else '禁用'}")
print(f"✓ 最小本体长度: {MIN_TENOR_LENGTH} | 最小喻体长度: {MIN_VEHICLE_LENGTH}")
print("=" * 80)

for filename in sorted(os.listdir(input_dir)):
    if filename.startswith("cleaned_") and filename.endswith(".txt"):
        year_match = re.search(r"(\d{4})", filename)
        if not year_match:
            continue
        year = year_match.group(1)
        filepath = os.path.join(input_dir, filename)

        stats['files'] += 1
        print(f"\n📄 {filename} (年份: {year})")

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        file_count = 0
        file_rejected = 0

        for line_num, line in enumerate(lines, 1):
            text = line.strip()
            if not text:
                continue

            stats['lines'] += 1

            if LOG_REJECTIONS:
                metaphors, rejections = extract_metaphors_with_logging(text, year, filename, line_num)
                all_rejected.extend(rejections)
                file_rejected += len(rejections)
                for rej in rejections:
                    rejection_reasons[rej['rejection_reason']] += 1
            else:
                metaphors = extract_metaphors(text)

            for meta in metaphors:
                all_results.append({
                    "年份": year,
                    "文件": filename,
                    "行号": line_num,
                    "原文": text,
                    "本体_TENOR": meta['tenor'],
                    "比喻词_COMPARATOR": meta['comparator'],
                    "喻体_VEHICLE": meta['vehicle'],
                    "上下文_CONTEXT": meta['context'],
                    "提取模式": meta['pattern'],
                    "置信度": meta['confidence'],
                    "验证原因": meta.get('validation', '')
                })
                file_count += 1
                stats['metaphors'] += 1

        if file_count > 0 or file_rejected > 0:
            print(f"   ✓ {file_count} 条比喻 接受")
            if file_rejected > 0:
                print(f"   ⊘ {file_rejected} 条比喻 拒绝")

# === SAVE RESULTS ===
print("\n" + "=" * 80)
print(f"📊 总计统计:")
print(f"   文件: {stats['files']}")
print(f"   处理行数: {stats['lines']}")
print(f"   ✓ 接受的比喻: {stats['metaphors']}")
print(f"   ⊘ 拒绝的比喻: {len(all_rejected)}")
print(f"   总提取率: {stats['metaphors'] + len(all_rejected)}")

if all_results:
    df = pd.DataFrame(all_results)

    print("\n📈 比喻词分布 (Top 20):")
    comp_counts = df["比喻词_COMPARATOR"].value_counts()
    for comp, count in comp_counts.head(20).items():
        percentage = (count / len(df)) * 100
        print(f"   {comp:12s}: {count:4d} ({percentage:5.2f}%)")

    # Verify no standalone 是
    shi_count = df[df['比喻词_COMPARATOR'] == '是'].shape[0]
    if shi_count > 0:
        print(f"\n⚠️  警告: 发现 {shi_count} 个单独的'是' (不应该有)")
    else:
        print(f"\n✓ 确认: 没有单独的'是'作为比喻词")

    # Show emphatic patterns with 是
    emphatic_shi = df[df['比喻词_COMPARATOR'].str.contains('是', na=False)]
    if len(emphatic_shi) > 0:
        print(f"✓ 强调性'是'模式: {len(emphatic_shi)} 个 (例如: 简直就是)")

    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n✅ 保存接受的比喻: {output_csv}")
else:
    print("\n⚠️  未提取到比喻")

# === SAVE REJECTIONS ===
if LOG_REJECTIONS and all_rejected:
    df_rejected = pd.DataFrame(all_rejected)
    df_rejected.to_csv(rejected_csv, index=False, encoding="utf-8-sig")
    print(f"✅ 保存拒绝日志: {rejected_csv}")

    print("\n📉 拒绝原因分布:")
    for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1])[:15]:
        percentage = (count / len(all_rejected)) * 100
        print(f"   {reason:50s}: {count:4d} ({percentage:5.2f}%)")

print("\n" + "=" * 80)
print("✅ 完成!")
print("=" * 80)
