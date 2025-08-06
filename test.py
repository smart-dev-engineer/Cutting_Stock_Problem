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

# --- UI 함수 ---
def add_item():
    """세션 상태에 새로운 품목을 추가합니다."""
    new_id = str(uuid.uuid4())
    st.session_state.item_list.append(
        {'id': new_id, 'name': '', 'length': 1000, 'count': 10, 'over': 0}
    )

def delete_item(item_id):
    """지정된 ID의 품목을 세션 상태에서 삭제합니다."""
    st.session_state.item_list = [item for item in st.session_state.item_list if item['id'] != item_id]

# --- UI 구성 ---
st.title("✂️ 원자재 절단 최적화")
st.info("각 품목 옆의 '➖' 버튼으로 삭제할 수 있습니다. 품목명은 고유해야 합니다.")

st.subheader("📦 원자재 정보")
cols_form = st.columns(2)
raw_length = cols_form[0].number_input("원자재 길이 (mm)", value=6000, min_value=1, key="raw_length")
cut_margin = cols_form[1].number_input("절단면 손실 (mm)", value=5, min_value=0, key="cut_margin")
st.markdown("---")

st.subheader("📋 품목 정보")
header_cols = st.columns([3, 2, 2, 2, 1])
header_cols[0].write("**품목명**")
header_cols[1].write("**길이 (mm)**")
header_cols[2].write("**수량**")
header_cols[3].write("**허용 초과**")

items_to_process = []
for i, item in enumerate(st.session_state.item_list):
    cols = st.columns([3, 2, 2, 2, 1])
    # 각 위젯의 값을 세션 상태와 동기화
    item['name'] = cols[0].text_input("품목명", value=item['name'], key=f"name_{item['id']}", label_visibility="collapsed")
    item['length'] = cols[1].number_input("길이", value=item['length'], min_value=1, key=f"length_{item['id']}", label_visibility="collapsed")
    item['count'] = cols[2].number_input("수량", value=item['count'], min_value=1, key=f"count_{item['id']}", label_visibility="collapsed")
    item['over'] = cols[3].number_input("허용초과", value=item['over'], min_value=0, key=f"over_{item['id']}", label_visibility="collapsed")
    
    cols[4].button("➖", key=f"del_{item['id']}", on_click=delete_item, args=(item['id'],))

    if item['name']:
        items_to_process.append(item)

st.button("➕ 품목 추가", on_click=add_item)
st.markdown("---")

submitted = st.button("✅ 최적화 실행", type="primary")

# --- 핵심 로직 ---
def generate_patterns(items, raw_length, cut_margin):
    """itertools.product를 사용하여 가능한 모든 절단 패턴을 생성합니다."""
    max_counts = [(raw_length // item['length']) if item['length'] > 0 else 0 for item in items]
    patterns = []
    
    ranges = [range(m + 1) for m in max_counts]
    
    for combo in product(*ranges):
        total_pieces = sum(combo)
        if total_pieces == 0:
            continue
        
        pieces_length = sum(combo[i] * items[i]['length'] for i in range(len(items)))
        # *** 수정: 절단 횟수를 품목 수(total_pieces)로 계산 ***
        cut_loss = cut_margin * total_pieces
        total_len = pieces_length + cut_loss
        
        if total_len <= raw_length:
            pattern = {items[i]['name']: combo[i] for i in range(len(items))}
            pattern['used_length'] = total_len # 물리적으로 사용된 총 길이 (제품+절단면)
            patterns.append(pattern)
            
    return patterns

def optimize(items, patterns):
    """OR-Tools를 사용하여 최적화 문제를 해결하고 구조화된 결과를 반환합니다."""
    solver = pywraplp.Solver.CreateSolver('SCIP')
    x = [solver.IntVar(0, solver.infinity(), f'x_{i}') for i in range(len(patterns))]
    
    for item in items:
        name = item['name']
        min_required = item['count']
        max_allowed = item['count'] + item['over']
        
        produced_amount = sum(x[i] * patterns[i].get(name, 0) for i in range(len(patterns)))
        solver.Add(produced_amount >= min_required)
        solver.Add(produced_amount <= max_allowed)
        
    solver.Minimize(solver.Sum(x))
    status = solver.Solve()
    
    solution = []
    if status == pywraplp.Solver.OPTIMAL:
        for i, pattern in enumerate(patterns):
            count = int(x[i].solution_value())
            if count > 0:
                # 패턴과 카운트를 묶어서 저장 (더 안정적인 구조)
                solution.append({'pattern': pattern, 'count': count})
    return solution

def show_cutting_visual(solution, items, raw_length, cut_margin):
    """절단 패턴을 시각화합니다. 구조화된 solution을 직접 사용합니다."""
    if not solution:
        return

    # 사용 횟수 기준으로 솔루션 정렬
    sorted_solution = sorted(solution, key=lambda x: x['count'], reverse=True)

    fig, axes = plt.subplots(len(sorted_solution), 1, figsize=(10, len(sorted_solution) * 0.8), squeeze=False)
    axes = axes.flatten()

    color_map = plt.cm.get_cmap('Pastel1', len(items))
    item_colors = {item['name']: color_map(i) for i, item in enumerate(items)}

    for idx, sol in enumerate(sorted_solution):
        ax = axes[idx]
        pos = 0
        pattern = sol['pattern']
        count = sol['count']
        used_length = pattern['used_length']
        
        # 패턴 딕셔너리에서 직접 품목 정보 처리
        pattern_items = sorted((name, qty) for name, qty in pattern.items() if isinstance(qty, int) and qty > 0)
        
        for name, qty in pattern_items:
            try:
                length = next(i['length'] for i in items if i['name'] == name)
            except StopIteration:
                continue

            for _ in range(qty):
                # 품목 그리기
                ax.barh(0, length, left=pos, color=item_colors.get(name, 'gray'), edgecolor='black', linewidth=0.5)
                ax.text(pos + length / 2, 0, f"{name}\n({length})", va='center', ha='center', fontsize=8, color='black')
                pos += length
                
                # *** 수정: 모든 품목 뒤에 절단면 공간 추가 ***
                pos += cut_margin
        
        # 물리적인 잔재 (그래프 표시용)
        physical_leftover = raw_length - pos
        if physical_leftover > 0.1:
            ax.barh(0, physical_leftover, left=pos, color='lightgray', hatch='//', edgecolor='gray')
            ax.text(pos + physical_leftover / 2, 0, f"잔재\n({physical_leftover:.0f})", va='center', ha='center', fontsize=8, color='black')

        ax.set_xlim(0, raw_length)
        ax.set_yticks([])
        # 제목의 '잔재'는 (원자재 길이 - 사용 길이)으로 계산
        ax.set_title(f"패턴-{idx+1:02d} (🔁 {count}회 / 사용: {used_length}mm / 잔재: {raw_length - used_length}mm)", loc='left', fontsize=10)
        ax.axis('off')

    plt.tight_layout(pad=2.0)
    st.pyplot(fig)

# --- 실행 로직 ---
if submitted:
    names = [item['name'] for item in items_to_process]
    if len(names) != len(set(names)):
        st.error("🚫 오류: 품목명이 중복되었습니다. 각 품목의 이름은 고유해야 합니다.")
    elif not items_to_process:
        st.error("⚠️ 하나 이상의 품목을 입력해야 합니다.")
    else:
        try:
            with st.spinner("최적화 중입니다... (품목 수가 많으면 오래 걸릴 수 있습니다)"):
                patterns = generate_patterns(items_to_process, raw_length, cut_margin)
                if not patterns:
                    st.error("❌ 유효한 절단 패턴을 생성할 수 없습니다.")
                else:
                    solution = optimize(items_to_process, patterns)
                    if not solution:
                        st.error("❌ 최적화 실패: 조건에 맞는 결과가 없습니다.")
                    else:
                        total_raws = sum(s['count'] for s in solution)
                        st.success(f"✅ 최적화 완료! 총 {total_raws}개의 원자재가 필요합니다.")
                        
                        # --- 결과 분석 및 표시 ---
                        st.subheader("📊 품목별 생산 분석")
                        actual_counts = {name: 0 for name in names}
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

                        # "절단 패턴 요약" 테이블 형식 수정
                        st.subheader("📘 절단 패턴 요약")
                        summary_data = []
                        for sol in solution:
                            pattern = sol['pattern']
                            pattern_desc = ", ".join(f"{name}={qty}" for name, qty in pattern.items() if isinstance(qty, int) and qty > 0)
                            used_length = pattern['used_length']
                            summary_data.append({
                                "패턴 구성": pattern_desc,
                                "사용 횟수": sol['count'],
                                "사용 길이": used_length,
                                "자투리": raw_length - used_length
                            })
                        
                        # 데이터프레임 생성
                        summary_df = pd.DataFrame(summary_data)
                        
                        # '사용 횟수' 기준으로 내림차순 정렬
                        if not summary_df.empty:
                            summary_df = summary_df.sort_values(by="사용 횟수", ascending=False).reset_index(drop=True)

                        # 컬럼 순서 지정 및 출력
                        columns_order = ["패턴 구성", "사용 횟수", "사용 길이", "자투리"]
                        st.dataframe(summary_df[columns_order], use_container_width=True, hide_index=True)


                        st.subheader("📐 절단 시각화")
                        show_cutting_visual(solution, items_to_process, raw_length, cut_margin)

        except Exception as e:
            st.error(f"🚫 예상치 못한 오류가 발생했습니다: {e}")
            import traceback
            st.code(traceback.format_exc())
