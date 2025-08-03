import streamlit as st
from ortools.linear_solver import pywraplp
from itertools import product
import matplotlib.pyplot as plt
import platform
from collections import defaultdict

# 한글 폰트 설정
def set_korean_font():
    if platform.system() == 'Windows':
        plt.rcParams['font.family'] = 'Malgun Gothic'
    elif platform.system() == 'Darwin':
        plt.rcParams['font.family'] = 'AppleGothic'
    else:
        plt.rcParams['font.family'] = 'NanumGothic'
    plt.rcParams['axes.unicode_minus'] = False

set_korean_font()

st.set_page_config(page_title="절단 최적화", layout="wide")
st.title("✂️ 원자재 절단 최적화")

# 품목 개수 관리
if "num_items" not in st.session_state:
    st.session_state.num_items = 3

if st.button("➕ 품목 추가"):
    st.session_state.num_items += 1

# 📋 입력 폼
with st.form("input_form"):
    st.subheader("📦 품목 입력")
    raw_length = st.number_input("원자재 길이 (mm)", value=6000)
    cut_margin = st.number_input("절단면 손실 (mm)", value=5)

    items = []
    for i in range(st.session_state.num_items):
        cols = st.columns(4)
        name = cols[0].text_input(f"품목명 {i+1}", value=f"A{i+1}" if i < 3 else "", key=f"name_{i}")
        length = cols[1].number_input(f"길이 {i+1}", min_value=1, value=[1402, 2034, 1300][i] if i < 3 else 1000, key=f"length_{i}")
        count = cols[2].number_input(f"수량 {i+1}", min_value=1, value=[24, 21, 54][i] if i < 3 else 10, key=f"count_{i}")
        over_allow = cols[3].number_input(f"허용 초과 {i+1}", min_value=0, value=0, key=f"over_{i}")
        items.append({'name': name, 'length': int(length), 'count': int(count), 'over': int(over_allow)})

    submitted = st.form_submit_button("✅ 최적화 실행")

# 최적화 및 시각화
if submitted:
    try:
        item_names = [item['name'] for item in items]

        def generate_patterns():
            max_counts = [raw_length // item['length'] for item in items]
            patterns = []
            for combo in product(*[range(m + 1) for m in max_counts]):
                total_pieces = sum(combo)
                if total_pieces == 0:
                    continue
                cut_loss = cut_margin * (total_pieces - 1)
                total_len = sum(combo[i] * items[i]['length'] for i in range(len(items))) + cut_loss
                if total_len <= raw_length:
                    pattern = {items[i]['name']: combo[i] for i in range(len(items))}
                    pattern['used_length'] = total_len
                    patterns.append(pattern)
            return patterns

        def optimize(patterns):
            solver = pywraplp.Solver.CreateSolver('SCIP')
            x = [solver.IntVar(0, solver.infinity(), f'x_{i}') for i in range(len(patterns))]
            for item in items:
                name = item['name']
                min_required = item['count']
                max_allowed = item['count'] + item['over']
                solver.Add(sum(x[i] * patterns[i][name] for i in range(len(patterns))) >= min_required)
                solver.Add(sum(x[i] * patterns[i][name] for i in range(len(patterns))) <= max_allowed)
            solver.Minimize(solver.Sum(x))
            status = solver.Solve()
            result = []
            if status == pywraplp.Solver.OPTIMAL:
                for i, pattern in enumerate(patterns):
                    count = int(x[i].solution_value())
                    for _ in range(count):
                        result.append(pattern)
            return result

        def show_cutting_visual(result_patterns):
            pattern_counts = defaultdict(int)
            pattern_order = []
            for pattern in result_patterns:
                key = tuple((name, pattern[name]) for name in item_names)
                pattern_counts[key] += 1
                if key not in pattern_order:
                    pattern_order.append(key)

            color_map = ['skyblue', 'lightgreen', 'orange', 'violet', 'khaki', 'lightcoral']
            item_colors = {name: color_map[i % len(color_map)] for i, name in enumerate(item_names)}
            leftover_color = 'red'

            fig, axes = plt.subplots(len(pattern_order), 1, figsize=(10, len(pattern_order) * 0.6))
            if len(pattern_order) == 1:
                axes = [axes]

            for idx, key in enumerate(pattern_order):
                ax = axes[idx]
                pos = 0
                pattern = {name: qty for name, qty in key}
                total_pieces = sum(qty for _, qty in key)
                used_length = sum(
                    pattern[name] * next(item['length'] for item in items if item['name'] == name)
                    for name in item_names
                ) + cut_margin * (total_pieces - 1 if total_pieces > 0 else 0)

                seq = []
                for name in item_names:
                    seq.extend([name] * pattern[name])
                for j, name in enumerate(seq):
                    length = next(i['length'] for i in items if i['name'] == name)
                    ax.barh(0, length, left=pos, color=item_colors[name])
                    ax.text(pos + length / 2, 0, name, va='center', ha='center', fontsize=8)
                    pos += length
                    if j < len(seq) - 1:
                        pos += cut_margin

                leftover = raw_length - pos
                if leftover > 0:
                    ax.barh(0, leftover, left=pos, color=leftover_color)

                repeat = pattern_counts[key]
                ax.set_xlim(0, raw_length)
                ax.set_title(f"패턴-{idx+1:02d} (🔁 {repeat}회 / 사용: {pos}mm / 잔재: {leftover}mm)")
                ax.axis('off')

            plt.tight_layout()
            st.pyplot(fig)

        with st.spinner("최적화 중..."):
            patterns = generate_patterns()
            result_patterns = optimize(patterns)

        if not result_patterns:
            st.error("❌ 최적화 실패: 조건에 맞는 결과가 없습니다.")
        else:
            st.success(f"✅ 최적화 완료! 원자재 사용 수: {len(result_patterns)}")

            st.subheader("📊 품목별 생산 분석")
            actual_counts = {name: 0 for name in item_names}
            for pattern in result_patterns:
                for name in item_names:
                    actual_counts[name] += pattern[name]

            diff_table = []
            for item in items:
                name = item['name']
                actual = actual_counts[name]
                required = item['count']
                diff = actual - required
                status = "충족" if diff == 0 else ("초과" if diff > 0 else "부족")
                diff_table.append({
                    "품목": name,
                    "요구 수량": required,
                    "생산 수량": actual,
                    "상태": status,
                    "차이": abs(diff)
                })
            st.dataframe(diff_table, use_container_width=True)

            st.subheader("📘 절단 패턴 요약")
            pattern_summary = defaultdict(lambda: {'count': 0, 'used_length': 0})
            for pattern in result_patterns:
                key = tuple((name, pattern[name]) for name in item_names)
                pattern_summary[key]['count'] += 1
                pattern_summary[key]['used_length'] = pattern['used_length']

            summary_table = []
            for key, value in pattern_summary.items():
                pattern_desc = ", ".join(f"{name}={qty}" for name, qty in key if qty > 0)
                summary_table.append({
                    "패턴 구성": pattern_desc,
                    "사용 횟수": value['count'],
                    "사용 길이": value['used_length'],
                    "자투리": raw_length - value['used_length']
                })
            st.dataframe(summary_table, use_container_width=True)

            st.subheader("📐 절단 시각화")
            show_cutting_visual(result_patterns)

    except Exception as e:
        st.error(f"🚫 오류 발생: {e}")
