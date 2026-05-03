package com.fitness.tracker;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

final class Normalizer {
    private static final Map<String, String> ALIASES = new HashMap<>();
    private static final Map<String, String> BODY_PARTS = new HashMap<>();

    static {
        ALIASES.put("杠精卧推", "杠铃卧推");
        ALIASES.put("杠精划船", "杠铃划船");
        ALIASES.put("奥氏引体", "澳式引体");
        ALIASES.put("澳氏引体", "澳式引体");
        ALIASES.put("引体", "引体向上");
        ALIASES.put("上斜哑铃", "上斜哑铃卧推");
        ALIASES.put("哑铃上斜卧推", "上斜哑铃卧推");
        ALIASES.put("飞鸟下夹胸", "飞鸟夹下胸");
        ALIASES.put("飞鸟夹胸下胸", "飞鸟夹下胸");
        ALIASES.put("反身龙门架卷腹", "反向龙门架卷腹");
        ALIASES.put("杠铃划船，", "杠铃划船");
        ALIASES.put("引体向上2 3不标准", "引体向上");
        ALIASES.put("半握引体向上", "引体向上");
        ALIASES.put("宽距引体", "引体向上");
        ALIASES.put("窄距引体", "引体向上");
        ALIASES.put("半程引体", "引体向上");
        ALIASES.put("辅助引体", "引体向上");

        BODY_PARTS.put("杠铃卧推", "胸");
        BODY_PARTS.put("杠铃划船", "背");
        BODY_PARTS.put("澳式引体", "背");
        BODY_PARTS.put("引体向上", "背");
        BODY_PARTS.put("上斜哑铃卧推", "胸");
        BODY_PARTS.put("飞鸟夹下胸", "胸");
        BODY_PARTS.put("反向龙门架卷腹", "核心");
        BODY_PARTS.put("俯卧撑", "胸");
        BODY_PARTS.put("负重俯卧撑", "胸");
        BODY_PARTS.put("杠铃深蹲", "腿");
        BODY_PARTS.put("高脚杯深蹲", "腿");
        BODY_PARTS.put("高脚杯哑铃深蹲", "腿");
        BODY_PARTS.put("哑铃深蹲", "腿");
        BODY_PARTS.put("自重深蹲", "腿");
        BODY_PARTS.put("杠铃硬拉", "腿");
        BODY_PARTS.put("罗马尼亚硬拉", "腿");
        BODY_PARTS.put("杠铃弯举", "手臂");
        BODY_PARTS.put("哑铃弯举", "手臂");
        BODY_PARTS.put("实力推", "肩");
        BODY_PARTS.put("卷腹", "核心");
        BODY_PARTS.put("负重卷腹", "核心");
        BODY_PARTS.put("龙门架卷腹", "核心");
        BODY_PARTS.put("高位下拉", "背");
        BODY_PARTS.put("坐姿划船", "背");
        BODY_PARTS.put("哑铃划船", "背");
        BODY_PARTS.put("单臂划船", "背");
        BODY_PARTS.put("单臂下拉", "背");
        BODY_PARTS.put("飞鸟夹胸", "胸");
        BODY_PARTS.put("哑铃侧平举", "肩");
        BODY_PARTS.put("反向箭步蹲", "腿");
        BODY_PARTS.put("哑铃卧推", "胸");
    }

    private Normalizer() {
    }

    static String clean(String value) {
        if (value == null) {
            return "";
        }
        return value.trim().replaceAll("\\s+", " ");
    }

    static String exercise(String value) {
        String clean = clean(value);
        String alias = ALIASES.get(clean);
        return alias == null ? clean : alias;
    }

    static String bodyPart(String exercise, String fallback) {
        String preferred = BODY_PARTS.get(exercise(exercise));
        if (preferred != null) {
            return preferred;
        }
        String cleanFallback = clean(fallback);
        return cleanFallback.isEmpty() ? "其他" : cleanFallback;
    }

    static List<String> aliasesFor(String exercise) {
        String canonical = exercise(exercise);
        List<String> names = new ArrayList<>();
        if (!canonical.isEmpty()) {
            names.add(canonical);
        }
        String input = clean(exercise);
        if (!input.isEmpty() && !names.contains(input)) {
            names.add(input);
        }
        for (Map.Entry<String, String> entry : ALIASES.entrySet()) {
            if (entry.getValue().equals(canonical) && !names.contains(entry.getKey())) {
                names.add(entry.getKey());
            }
        }
        return names;
    }
}
