
import re
import streamlit as st

st.set_page_config(
    page_title="광고·홍보물 자동 채점",
    page_icon="📝",
    layout="wide"
)

# ------------------------------------------------------------
# 1) 공통 유틸리티
# ------------------------------------------------------------

def normalize(text: str) -> str:
    """띄어쓰기·문장부호 차이를 줄여 비교하기 위한 간단한 정규화."""
    text = (text or "").lower().strip()
    text = re.sub(r"[·ㆍ•,.'\"“”‘’!?~:;()\[\]{}<>/\-_]", "", text)
    text = re.sub(r"\s+", "", text)
    return text


def contains_any(text: str, expressions):
    """표현 후보 중 하나라도 답안에 포함되면 True."""
    t = normalize(text)
    return any(normalize(exp) in t for exp in expressions)


def group_hit(text: str, group):
    """하나의 의미군 안에서 하나 이상의 표현이 맞는지 확인."""
    return contains_any(text, group)


def all_groups_hit(text: str, groups):
    """모든 필수 의미군이 충족되는지 확인."""
    return all(group_hit(text, g) for g in groups)


def any_group_hit(text: str, groups):
    """여러 대안 의미군 중 하나라도 충족되는지 확인."""
    return any(group_hit(text, g) for g in groups)


def misconception_hit(text: str, misconception_groups):
    """오개념/개념 혼동 표현 감지."""
    return any(group_hit(text, g) for g in misconception_groups)


# ------------------------------------------------------------
# 2) 채점 규칙
#    - required_all: 모두 충족해야 하는 의미군
#    - required_any: 여러 대안 중 하나 이상 충족
#    - forbidden: 오개념·개념 혼동·결론 반전
# ------------------------------------------------------------

from shared_config import RULES, MEDIA




# ------------------------------------------------------------
# 3) 광고 자료(영상/이미지)
# ------------------------------------------------------------

def show_media(ad_name):
    """선택한 광고의 영상 또는 이미지를 문항 위에 표시."""
    media = MEDIA.get(ad_name)

    if not media:
        return

    st.subheader("🎬 광고 자료")

    if media["type"] == "video":
        st.video(media["src"])
    elif media["type"] == "image":
        try:
            st.image(media["src"], use_container_width=True)
        except Exception:
            st.warning(
                "광고 이미지 파일을 불러오지 못했습니다. "
                "GitHub 저장소의 media 폴더에 이미지 파일이 있는지 확인해 주세요."
            )

    st.caption(media.get("caption", ""))
    st.divider()


# ------------------------------------------------------------
# 3) 채점 함수
# ------------------------------------------------------------

def grade_answer(rule, answer):
    answer = answer or ""

    if not answer.strip():
        return False, "답안을 입력하지 않았습니다."

    # 오개념/개념 혼동 우선 차단
    if misconception_hit(answer, rule.get("forbidden", [])):
        return False, "문항에서 요구한 개념과 다른 개념의 설명이 포함되어 있습니다."

    # 모든 필수 의미군
    required_all = rule.get("required_all", [])
    if required_all and not all_groups_hit(answer, required_all):
        return False, "필수 의미 요소가 충분히 드러나지 않았습니다."

    # 선택지형: 여러 대안 중 하나
    required_any = rule.get("required_any", [])
    if required_any and not any_group_hit(answer, required_any):
        return False, "정답으로 인정되는 핵심 의미 또는 표현이 포함되지 않았습니다."

    # 결론 방향이 필요한 문항
    conclusion_any = rule.get("conclusion_any", [])
    if conclusion_any and not any_group_hit(answer, conclusion_any):
        return False, "제작자의 최종 목적이나 행동 변화의 방향이 명확하지 않습니다."

    return True, "핵심 의미가 충족되었습니다."


# ------------------------------------------------------------
# 4) 순차 학습 진행 함수
# ------------------------------------------------------------

AD_NAMES = list(RULES.keys())

def get_question_names(ad_idx):
    return list(RULES[AD_NAMES[ad_idx]].keys())

def advance_to_next_question():
    """정답을 맞힌 뒤 다음 문항/다음 광고로 자동 이동."""
    ad_idx = st.session_state.current_ad_idx
    q_idx = st.session_state.current_q_idx
    questions = get_question_names(ad_idx)

    if q_idx < len(questions) - 1:
        # 같은 광고의 다음 문항
        st.session_state.current_q_idx += 1
        st.session_state.flash_message = "✅ 정답입니다! 다음 문항으로 이동했습니다."
    elif ad_idx < len(AD_NAMES) - 1:
        # 다음 광고의 1번 문항
        st.session_state.current_ad_idx += 1
        st.session_state.current_q_idx = 0
        next_ad = AD_NAMES[st.session_state.current_ad_idx]
        st.session_state.flash_message = f"🎉 이 광고의 문항을 모두 풀었습니다! 다음 광고로 이동합니다: {next_ad}"
    else:
        # 마지막 광고의 마지막 문항까지 완료
        st.session_state.completed = True
        st.session_state.flash_message = "🏆 모든 광고의 문항을 완료했습니다!"

def reset_learning():
    """처음부터 다시 시작."""
    keys_to_delete = [
        k for k in st.session_state.keys()
        if k.startswith("attempts::") or k.startswith("answer::")
    ]
    for k in keys_to_delete:
        del st.session_state[k]

    st.session_state.current_ad_idx = 0
    st.session_state.current_q_idx = 0
    st.session_state.completed = False
    st.session_state.flash_message = "처음부터 다시 시작합니다."
    st.session_state.first_try_correct = 0
    st.session_state.wrong_questions = 0
    st.session_state.total_wrong_attempts = 0


# ------------------------------------------------------------
# 5) Streamlit UI
# ------------------------------------------------------------

st.title("📝 광고·홍보물 분석 학습")
st.caption("중학교 2학년 국어 | 학생용")

st.info(
    "문항을 맞히면 자동으로 다음 문항으로 이동합니다. "
    "한 광고의 문항을 모두 풀면 다음 광고로 자동 이동합니다. "
    "같은 문항을 두 번 틀리면 모범답안과 채점 기준을 확인할 수 있습니다. "
    "화면 위에서 첫 시도 정답 수와 한 번 이상 틀린 문항 수를 확인할 수 있습니다."
)

# 진행 상태 초기화
if "current_ad_idx" not in st.session_state:
    st.session_state.current_ad_idx = 0
if "current_q_idx" not in st.session_state:
    st.session_state.current_q_idx = 0
if "completed" not in st.session_state:
    st.session_state.completed = False
if "flash_message" not in st.session_state:
    st.session_state.flash_message = ""

# 성취 기록
# first_try_correct: 첫 시도에 바로 맞힌 문항 수
# wrong_questions: 한 번 이상 오답이 발생한 문항 수(문항별 1회만 집계)
# total_wrong_attempts: 전체 오답 시도 횟수
if "first_try_correct" not in st.session_state:
    st.session_state.first_try_correct = 0
if "wrong_questions" not in st.session_state:
    st.session_state.wrong_questions = 0
if "total_wrong_attempts" not in st.session_state:
    st.session_state.total_wrong_attempts = 0

# 이전 채점 결과에 따른 안내 메시지
if st.session_state.flash_message:
    st.success(st.session_state.flash_message)
    st.session_state.flash_message = ""

# 전체 진행률 계산
total_questions = sum(len(qs) for qs in RULES.values())
completed_before = 0
for i in range(st.session_state.current_ad_idx):
    completed_before += len(RULES[AD_NAMES[i]])
completed_before += st.session_state.current_q_idx

if st.session_state.completed:
    completed_count = total_questions
else:
    completed_count = completed_before

progress = completed_count / total_questions if total_questions else 0
st.progress(progress)
st.caption(f"전체 진행: {completed_count} / {total_questions} 문항 완료")

score_col1, score_col2, score_col3 = st.columns(3)
with score_col1:
    st.metric("✅ 첫 시도 정답", st.session_state.first_try_correct)
with score_col2:
    st.metric("❌ 틀린 문항", st.session_state.wrong_questions)
with score_col3:
    st.metric("🔁 총 오답 시도", st.session_state.total_wrong_attempts)

# 모든 문항 완료 화면
if st.session_state.completed:
    st.balloons()
    st.success("🎉 1번 광고부터 4번 광고까지 모든 문항을 완료했습니다!")

    st.subheader("🏅 최종 결과")
    final_col1, final_col2, final_col3 = st.columns(3)
    with final_col1:
        st.metric("✅ 첫 시도 정답", st.session_state.first_try_correct)
    with final_col2:
        st.metric("❌ 틀린 문항", st.session_state.wrong_questions)
    with final_col3:
        st.metric("🔁 총 오답 시도", st.session_state.total_wrong_attempts)

    st.write(
        f"총 **{total_questions}문항** 중 "
        f"**{st.session_state.first_try_correct}문항을 첫 시도에 맞혔습니다.** "
        f"한 번 이상 틀린 문항은 **{st.session_state.wrong_questions}문항**입니다."
    )

    if st.button("처음부터 다시 풀기", use_container_width=True):
        reset_learning()
        st.rerun()

else:
    ad_idx = st.session_state.current_ad_idx
    q_idx = st.session_state.current_q_idx

    ad_name = AD_NAMES[ad_idx]
    question_names = get_question_names(ad_idx)
    question_name = question_names[q_idx]
    rule = RULES[ad_name][question_name]

    st.markdown(f"### {ad_name}")
    st.caption(
        f"현재 위치: 광고 {ad_idx + 1} / {len(AD_NAMES)} · "
        f"문항 {q_idx + 1} / {len(question_names)}"
    )

    # 선택한 광고의 영상/이미지를 문항 위에 표시
    show_media(ad_name)

    st.subheader(f"✏️ {question_name}")

    # 문항별 오답 횟수를 세션에 저장
    attempt_key = f"attempts::{ad_name}::{question_name}"
    if attempt_key not in st.session_state:
        st.session_state[attempt_key] = 0

    answer_key = f"answer::{ad_name}::{question_name}"
    answer = st.text_area(
        "학생 답안",
        height=130,
        placeholder="학생의 답안을 입력하세요.",
        key=answer_key
    )

    if st.button("채점하기", type="primary", use_container_width=True):
        passed, feedback = grade_answer(rule, answer)

        if passed:
            # 오답 없이 첫 시도에 맞힌 경우에만 첫 시도 정답으로 집계
            if st.session_state[attempt_key] == 0:
                st.session_state.first_try_correct += 1

            # 현재 문항 답안을 지우고 다음 문항으로 이동
            if answer_key in st.session_state:
                del st.session_state[answer_key]
            advance_to_next_question()
            st.rerun()

        else:
            # 이 문항의 첫 오답일 때만 '틀린 문항' 수를 1 증가
            if st.session_state[attempt_key] == 0:
                st.session_state.wrong_questions += 1

            st.session_state[attempt_key] += 1
            st.session_state.total_wrong_attempts += 1
            wrong_count = st.session_state[attempt_key]

            st.error(f"❌ 정답으로 인정하기 어렵습니다. (오답 {wrong_count}회)")
            st.write("**채점 피드백:**", feedback)

            # 2회 이상 틀린 경우에만 모범답안과 채점 기준 공개
            if wrong_count >= 2:
                st.warning("두 번 이상 틀렸습니다. 아래의 모범답안과 채점 기준을 확인해 보세요.")

                with st.expander("📌 모범 답안 및 채점 기준 보기", expanded=True):
                    st.markdown("**모범 답안**")
                    for i, ans in enumerate(rule["model_answers"], 1):
                        st.write(f"{i}. {ans}")

                    st.markdown("**채점 메모**")
                    st.write(rule["note"])
            else:
                st.info("한 번 더 생각해서 다시 답해 보세요. 모범답안은 두 번 틀렸을 때부터 확인할 수 있습니다.")



st.divider()

st.caption(
    "주의: 이 앱은 규칙 기반 채점기입니다. 학생이 매우 창의적인 문장으로 의미를 표현하면 "
    "현재 등록된 허용 표현에 없어서 오답 처리될 수 있습니다."
)
