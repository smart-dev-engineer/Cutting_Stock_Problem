import streamlit as st
from ortools.linear_solver import pywraplp
from itertools import product
import matplotlib.pyplot as plt
import platform
from collections import defaultdict
import pandas as pd
import uuid

# --- 초기 설정 ---
# 한글 폰트 설정
def set_korean_font():
    """운영체제에 맞는 한글 폰트를 설정합니다."""
    system_name = platform.system()
    if system_name == 'Windows':
        plt.rcParams['font.family'] = 'Malgun Gothic'
    elif system_name == 'Darwin': # macOS
        plt.rcParams['font.family'] = 'AppleGothic'
    else: # Linux
        plt.rcParams['font.family'] = 'NanumGothic'
    plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="절단 최적화", layout="wide")
set_korean_font()

# --- 세션 상태 관리 ---
if 'item_list' not in st.session_state:
    st.session_state.item_list = [
        {'id': str(uuid.uuid4()), 'name': 'A1', 'length': 1402, 'count': 24, 'over': 0},
        {'id': str(uuid.uuid4()), 'name': 'A2', 'length': 2034, 'count': 21, 'over': 0},
        {'id': str(uuid.uuid4()), 'name': 'A3', 'length': 1300, 'count': 54, 'over': 0},
    ]
if 'raw_material_list' not in st.session_state:
    st.session_state.raw_material_list = [
        {'id': str(uuid.uuid4()), 'name': '원자재A', 'length': 6000, 'stock': 100},
        {'id': str(uuid.uuid4()), 'name': '원자재B', 'length': 5000, 'stock': 100},
    ]

# --- UI 함수 ---
def add_item():
    st.session_state.item_list.append({'id': str(uuid.uuid4()), 'name': '', 'length': 1000, 'count': 10, 'over': 0})

def delete_item(item_id):
    st.session_state.item_list = [item for item in st.session_state.item_list if item['id'] != item_id]

def add_raw_material():
    st.session_state.raw_material_list.append({'id': str(uuid.uuid4()), 'name': '', 'length': 6000, 'stock': 100})

def delete_raw_material(raw_id):
    st.session_state.raw_material_list = [raw for raw in st.session_state.raw_material_list if raw['id'] != raw_id]


# --- UI 구성 ---
st.title("✂️ 다중 원자재 절단 최적화")
st.info("여러 종류의 원자재를 입력하고, 총 자투리를 최소화하는 최적의 조합을 찾습니다.")

# --- 원자재 정보 입력 UI ---
st.subheader("📦 원자재 정보")
raw_header_cols = st.columns([3, 2, 2, 1])
raw_header_cols[0].write("**원자재명**")
raw_header_cols[1].write("**길이 (mm)**")
raw_header_cols[2].write("**재고 수량**")

raw_materials_to_process = []
for raw in st.session_state.raw_material_list:
    raw_cols = st.columns([3, 2, 2, 1])
    raw['name'] = raw_cols[0].text_input("원자재명", value=raw['name'], key=f"raw_name_{raw['id']}", label_visibility="collapsed")
    raw['length'] = raw_cols[1].number_input("길이", value=raw['length'], min_value=1, key=f"raw_length_{raw['id']}", label_visibility="collapsed")
    raw['stock'] = raw_cols[2].number_input("재고", value=raw['stock'], min_value=1, key=f"raw_stock_{raw['id']}", label_visibility="collapsed")
    raw_cols[3].button("➖", key=f"del_raw_{raw['id']}", on_click=delete_raw_material, args=(raw['id'],))
    if raw['name']:
        raw_materials_to_process.append(raw)
st.button("➕ 원자재 추가", on_click=add_raw_material)
st.markdown("---")

# --- 품목 정보 입력 UI ---
st.subheader("📋 생산 품목 정보")
item_header_cols = st.columns([3, 2, 2, 2, 1])
item_header_cols[0].write("**품목명**")
item_header_cols[1].write("**길이 (mm)**")
item_header_cols[2].write("**필수 수량**")
item_header_cols[3].write("**허용 초과**")

items_to_process = []
for item in st.session_state.item_list:
    item_cols = st.columns([3, 2, 2, 2, 1])
    item['name'] = item_cols[0].text_input("품목명", value=item['name'], key=f"name_{item['id']}", label_visibility="collapsed")
    item['length'] = item_cols[1].number_input("길이", value=item['length'], min_value=1, key=f"length_{item['id']}", label_visibility="collapsed")
    item['count'] = item_cols[2].number_input("수량", value=item['count'], min_value=1, key=f"count_{item['id']}", label_visibility="collapsed")
    item['over'] = item_cols[3].number_input("허용초과", value=item['over'], min_value=0, key=f"over_{item['id']}", label_visibility="collapsed")
    item_cols[4].button("➖", key=f"del_item_{item['id']}", on_click=delete_item, args=(item['id'],))
    if item['name']:
        items_to_process.append(item)
st.button("➕ 품목 추가", on_click=add_item)
st.markdown("---")

cut_margin = st.number_input("절단면 손실 (mm)", value=5, min_value=0, key="cut_margin")
submitted = st.button("✅ 최적화 실행", type="primary")


# --- 핵심 로직 ---
def generate_patterns(items, max_raw_length, cut_margin):
    """itertools.product를 사용하여 가능한 모든 절단 패턴을 생성합니다."""
    max_counts = [(max_raw_length // item['length']) if item['length'] > 0 else 0 for item in items]
    patterns = []
    
    for combo in product(*[range(m + 1) for m in max_counts]):
        total_pieces = sum(combo)
        if total_pieces == 0:
            continue
        
        pieces_length = sum(combo[i] * items[i]['length'] for i in range(len(items)))
        cut_loss = cut_margin * total_pieces
        total_len = pieces_length + cut_loss
        
        if total_len <= max_raw_length:
            pattern = {items[i]['name']: combo[i] for i in range(len(items))}
            pattern['used_length'] = total_len
            patterns.append(pattern)
            
    return patterns

def optimize_multi_raw(items, patterns, raw_materials):
    """여러 종류의 원자재를 고려하여 총 자투리(waste)를 최소화하는 최적화를 수행합니다."""
    solver = pywraplp.Solver.CreateSolver('SCIP')
    
    # 변수 생성: x_ij = 패턴 i를 원자재 j에서 자르는 횟수
    x = {}
    for i, p in enumerate(patterns):
        for j, r in enumerate(raw_materials):
            if p['used_length'] <= r['length']:
                x[i, j] = solver.IntVar(0, solver.infinity(), f'x_{i}_{j}')

    # 제약 조건 1: 각 품목의 요구 수량 충족
    for item in items:
        name = item['name']
        min_required = item['count']
        max_allowed = item['count'] + item['over']
        
        produced_amount = sum(x[i, j] * patterns[i].get(name, 0) for i, j in x)
        solver.Add(produced_amount >= min_required)
        solver.Add(produced_amount <= max_allowed)

    # 제약 조건 2: 각 원자재의 재고 수량 초과 불가
    for j, r in enumerate(raw_materials):
        used_stock = sum(x[i, j] for i in range(len(patterns)) if (i, j) in x)
        solver.Add(used_stock <= r['stock'])
        
    # 목표 함수: 총 자투리(waste) 최소화
    total_waste = sum(x[i, j] * (raw_materials[j]['length'] - patterns[i]['used_length']) for i, j in x)
    solver.Minimize(total_waste)
    
    status = solver.Solve()
    
    solution = []
    if status == pywraplp.Solver.OPTIMAL:
        for (i, j), var in x.items():
            count = int(var.solution_value())
            if count > 0:
                solution.append({
                    'pattern': patterns[i],
                    'count': count,
                    'raw_material': raw_materials[j]
                })
    return solution

def show_cutting_visual(solution, items, all_raw_materials, cut_margin):
    """절단 패턴을 시각화합니다."""
    if not solution: return

    max_overall_length = max(r['length'] for r in all_raw_materials) if all_raw_materials else 6000

    sorted_solution = sorted(solution, key=lambda s: s['count'], reverse=True)

    fig, axes = plt.subplots(len(sorted_solution), 1, figsize=(10, len(sorted_solution) * 0.8), squeeze=False)
    axes = axes.flatten()

    color_map = plt.cm.get_cmap('Pastel1', len(items))
    item_colors = {item['name']: color_map(i) for i, item in enumerate(items)}

    for idx, sol in enumerate(sorted_solution):
        ax = axes[idx]
        pos = 0
        pattern = sol['pattern']
        count = sol['count']
        raw_material = sol['raw_material']
        raw_length = raw_material['length']
        used_length = pattern['used_length']
        
        pattern_items = sorted((name, qty) for name, qty in pattern.items() if isinstance(qty, int) and qty > 0)
        
        for name, qty in pattern_items:
            try:
                length = next(i['length'] for i in items if i['name'] == name)
            except StopIteration: continue

            for _ in range(qty):
                ax.barh(0, length, left=pos, color=item_colors.get(name, 'gray'), edgecolor='black', linewidth=0.5)
                ax.text(pos + length / 2, 0, f"{name}\n({length})", va='center', ha='center', fontsize=8, color='black')
                pos += length
                pos += cut_margin
        
        # *** 수정: 잔재 계산 및 시각화 로직 단순화 및 수정 ***
        leftover = raw_length - used_length
        start_of_leftover = used_length
        
        if leftover > 0.1:
            ax.barh(0, leftover, left=start_of_leftover, color='lightgray', hatch='//', edgecolor='gray')
            ax.text(start_of_leftover + leftover / 2, 0, f"잔재\n({leftover:.0f})", va='center', ha='center', fontsize=8, color='black')

        ax.set_xlim(0, max_overall_length)
        ax.set_yticks([])
        title = f"패턴-{idx+1:02d} (원자재: {raw_material['name']}) (🔁 {count}회 / 사용: {used_length}mm / 잔재: {raw_length - used_length}mm)"
        ax.set_title(title, loc='left', fontsize=10)
        ax.axis('off')

    plt.tight_layout(pad=2.0)
    st.pyplot(fig)


# --- 실행 로직 ---
if submitted:
    # 입력 유효성 검사
    item_names = [item['name'] for item in items_to_process]
    raw_names = [raw['name'] for raw in raw_materials_to_process]
    if len(item_names) != len(set(item_names)):
        st.error("🚫 오류: 품목명이 중복되었습니다.")
    elif len(raw_names) != len(set(raw_names)):
        st.error("🚫 오류: 원자재명이 중복되었습니다.")
    elif not items_to_process or not raw_materials_to_process:
        st.error("⚠️ 하나 이상의 품목과 원자재를 입력해야 합니다.")
    else:
        try:
            with st.spinner("최적화 중입니다... (품목/원자재 수가 많으면 오래 걸릴 수 있습니다)"):
                max_raw_length = max(r['length'] for r in raw_materials_to_process)
                patterns = generate_patterns(items_to_process, max_raw_length, cut_margin)
                
                if not patterns:
                    st.error("❌ 유효한 절단 패턴을 생성할 수 없습니다.")
                else:
                    solution = optimize_multi_raw(items_to_process, patterns, raw_materials_to_process)
                    if not solution:
                        st.error("❌ 최적화 실패: 조건에 맞는 결과가 없습니다.")
                    else:
                        st.success(f"✅ 최적화 완료!")
                        
                        # --- 결과 분석 및 표시 ---
                        st.subheader("📊 품목별 생산 분석")
                        actual_counts = {name: 0 for name in item_names}
                        for sol in solution:
                            for name, qty in sol['pattern'].items():
                                if name in actual_counts:
                                    actual_counts[name] += qty * sol['count']
                        
                        diff_data = []
                        for item in items_to_process:
                            actual = actual_counts[item['name']]
                            required = item['count']
                            diff = actual - required
                            status = "✅ 충족" if diff == 0 else ("🔼 초과" if diff > 0 else "❌ 부족")
                            diff_data.append([item['name'], required, actual, status, diff])
                        
                        diff_df = pd.DataFrame(diff_data, columns=["품목", "요구 수량", "생산 수량", "상태", "차이"])
                        st.dataframe(diff_df, use_container_width=True, hide_index=True)

                        st.subheader("📘 절단 패턴 요약")
                        summary_data = []
                        for sol in solution:
                            pattern = sol['pattern']
                            raw_material = sol['raw_material']
                            pattern_desc = ", ".join(f"{name}={qty}" for name, qty in pattern.items() if isinstance(qty, int) and qty > 0)
                            used_length = pattern['used_length']
                            summary_data.append({
                                "원자재": raw_material['name'],
                                "패턴 구성": pattern_desc,
                                "사용 횟수": sol['count'],
                                "사용 길이": used_length,
                                "자투리": raw_material['length'] - used_length
                            })
                        
                        summary_df = pd.DataFrame(summary_data)
                        if not summary_df.empty:
                            summary_df = summary_df.sort_values(by=["원자재", "사용 횟수"], ascending=[True, False]).reset_index(drop=True)

                        columns_order = ["원자재", "패턴 구성", "사용 횟수", "사용 길이", "자투리"]
                        st.dataframe(summary_df[columns_order], use_container_width=True, hide_index=True)

                        st.subheader("📐 절단 시각화")
                        show_cutting_visual(solution, items_to_process, raw_materials_to_process, cut_margin)

        except Exception as e:
            st.error(f"🚫 예상치 못한 오류가 발생했습니다: {e}")
            import traceback
            st.code(traceback.format_exc())
