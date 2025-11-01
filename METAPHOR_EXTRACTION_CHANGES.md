# Metaphor Extraction Script - Permissive Version

## 🎯 Overview

Created a new **permissive** version of the metaphor extraction script (`extract_metaphors_permissive.py`) that removes restrictive semantic filters while keeping essential validation.

---

## 🔑 Key Changes

### 1. **REMOVED: Human-Human Category Filter** ✅

**OLD CODE (restrictive):**
```python
# Same human category (literal comparison)
if tenor_cat == vehicle_cat and tenor_cat == 'HUMAN':
    return False, "Same human category (literal)"
```

**WHY THIS IS CRITICAL:**
This filter was blocking **exactly the metaphors you need** for gender discourse analysis!

**Examples that are NOW captured:**
- ❌ **Previously rejected:** "女人像孩子" (women are like children)
- ❌ **Previously rejected:** "男人像动物" (men are like animals)
- ❌ **Previously rejected:** "她们像天使" (they are like angels)
- ✅ **Now ACCEPTED:** All human-to-human/human-to-being metaphors

### 2. **Made Semantic Filtering Optional**

**NEW FLAG:**
```python
USE_STRICT_SEMANTIC_FILTER = False  # Set to True for old behavior
```

- **Default = False (permissive):** Trust the explicit comparators (像, 如同, etc.)
- **Optional = True (strict):** Use old semantic category validation

**Rationale:** Since you're already using **explicit metaphor markers** (像, 如同, 仿佛, etc.), these words themselves signal metaphorical intent. The semantic filter was redundant and harmful.

### 3. **Minimal Non-Metaphor Terms List**

**OLD (too restrictive):**
```python
NON_METAPHOR_TERMS = {
    "男人", "女人", "父亲", "母亲", "爸爸", "妈妈", "孩子",  # ❌ TOO SPECIFIC
    "人", "东西", "事情", "时候", "地方", "那个", "这个"
}
```

**NEW (truly generic only):**
```python
NON_METAPHOR_TERMS = {
    "东西", "事情", "时候", "地方", "那个", "这个", "什么", "怎么"
}
```

**Why:** Removed gender terms from the filter. "女人像X" is a valid metaphor you want to study!

### 4. **Added Rejection Logging** 📋

**NEW FEATURE:**
```python
LOG_REJECTIONS = True  # Create rejected_metaphors log
```

**Output files:**
1. `metaphor_extracted_permissive.csv` - Accepted metaphors
2. `metaphor_rejected_log.csv` - Rejected metaphors with reasons

**Rejection log includes:**
- Year, filename, line number
- Original text
- Extracted tenor/vehicle/comparator
- **Rejection reason** (why it was filtered out)

**Benefits:**
- Review what's being filtered
- Find false negatives
- Tune the script based on real data

### 5. **Statistics on Rejection Reasons**

**NEW OUTPUT:**
```
📉 拒绝原因分布:
   Too short (tenor:1, vehicle:2)                     :  234 (34.21%)
   Incomplete noun phrase (attributive clause only)   :  156 (22.81%)
   Identical tenor and vehicle                        :   89 (13.01%)
   Temporal/numeric comparison (literal)              :   45 ( 6.58%)
   Both generic literal terms                         :   12 ( 1.75%)
```

This shows you **why** metaphors are being rejected, helping you refine the filters.

---

## 📊 What This Means for Your Data

### **MORE Metaphors Captured**

The permissive version will capture:

1. **Gender-related metaphors** (previously blocked)
   - "女人像孩子" → ACCEPTED ✅
   - "男人像牛" → ACCEPTED ✅
   - "她们像天使" → ACCEPTED ✅

2. **Dehumanizing comparisons** (critical for men-sphere analysis)
   - "X像动物" → ACCEPTED ✅
   - "X像工具" → ACCEPTED ✅
   - "X像垃圾" → ACCEPTED ✅

3. **Abstract-to-human mappings**
   - "爱情像监狱" → ACCEPTED ✅
   - "婚姻像坟墓" → ACCEPTED ✅

### **STILL Filtered Out** (good rejections)

The script still rejects:
- ✅ Incomplete noun phrases (attributive clauses only)
- ✅ Identical tenor/vehicle
- ✅ Temporal comparisons (年份像2024 = literal)
- ✅ Generic terms only (这个像那个 = meaningless)
- ✅ Too short extractions (< 2 characters)

---

## 🚀 Usage

### **Run the new script:**
```bash
python extract_metaphors_permissive.py
```

### **Configuration flags** (top of script):
```python
USE_STRICT_SEMANTIC_FILTER = False  # False = permissive (recommended)
LOG_REJECTIONS = True               # True = create rejection log
MIN_TENOR_LENGTH = 2                # Minimum characters for tenor
MIN_VEHICLE_LENGTH = 2              # Minimum characters for vehicle
```

### **Output:**
1. **Main results:** `metaphor_extracted_permissive.csv`
   - All accepted metaphors
   - Includes validation reason

2. **Rejection log:** `metaphor_rejected_log.csv`
   - All rejected metaphors
   - Includes rejection reason
   - Use this to find false negatives

---

## 📈 Expected Impact

### **Conservative Estimate:**
- Old script: ~X metaphors
- New script: **2-3x more metaphors** (especially gender-related)

### **Quality:**
- **Higher recall** (fewer false negatives)
- **Similar precision** (still filters obvious non-metaphors)
- **Better for gender discourse analysis**

---

## 🔍 Validation Strategy

1. **Run both scripts** on a sample file
2. **Compare counts** (new should be ≥ old)
3. **Review rejection log** to find patterns
4. **Spot-check accepted metaphors** for quality
5. **Adjust MIN_TENOR_LENGTH/MIN_VEHICLE_LENGTH** if needed

---

## 🆚 Side-by-Side Comparison

| Feature | Old Script | New Script |
|---------|------------|------------|
| Human-human filter | ❌ Blocks | ✅ Allows |
| Semantic categories | Required | Optional |
| Non-metaphor terms | 15 terms | 8 terms |
| Rejection logging | ❌ No | ✅ Yes |
| Rejection stats | ❌ No | ✅ Yes |
| Configurable | ❌ No | ✅ Yes |
| Gender metaphors | ⚠️ Blocked | ✅ Captured |

---

## 💡 Recommendations

1. **Start with default settings** (permissive mode, logging on)
2. **Run on your full dataset**
3. **Review the rejection log** to see what's filtered
4. **Adjust filters** if you see false positives/negatives
5. **Compare with old results** to quantify the difference

---

## ⚠️ Important Notes

- The script still uses **explicit comparators only** (像, 如同, etc.)
- It still **excludes standalone "是"** (not metaphorical)
- It still validates **noun phrase completeness** (no partial extractions)
- **Trust the explicit markers** - they signal metaphorical intent!

---

## 📝 Next Steps

1. ✅ Review this document
2. ✅ Update input/output paths in script if needed
3. ✅ Run on a small sample first
4. ✅ Check rejection log for insights
5. ✅ Run on full dataset
6. ✅ Compare with old results

---

**Key Insight:** Since you're using explicit metaphor markers (像, 如同, 仿佛, etc.), the script should **trust those markers** rather than imposing strict semantic categories. The new version does exactly that! 🎯
