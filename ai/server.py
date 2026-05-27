import json
import re
import time
import torch
import gc
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

app = FastAPI()

# ── 모델 로드 (서버 시작할 때 한 번만 실행) ────────────────────────────────
print("모델 로딩 중...")

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="bfloat16",
    bnb_4bit_use_double_quant=True,
)

model_name = "Qwen/Qwen3.6-27B"
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    quantization_config=bnb_config,
    device_map="auto",
    trust_remote_code=True,
)
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

print("✅ 모델 로드 완료")


# ── 요청/응답 형식 정의 ────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str  # STT로 변환된 회의 텍스트


class GenerateResponse(BaseModel):
    cotent: str
    todo_list: list


# ── 회의록 생성 함수 ───────────────────────────────────────────────────────
def extract_minutes(meeting_text: str) -> dict:
    prompt = f"""[역할]
    너는 회의를 화자별로 분석한 원본 데이터를 분석하여 회의록을 작성하고, 해야 할 일 즉 태스크를 추출하는 Jira AI야
    한눈에 읽어도 누구나 바로 알 수 있을 정도로 완벽한 정리를 해내지. 해당 내용들은 jira 이슈에도 등록될 예정이야 그러니
    매우 깔끔하고 정확하게 추출해야해 중국어 일본어 절대 쓰지마.

    [미션]
    제공된 대화 텍스트를 분석하여 반드시 아래 JSON 형식으로만 응답해줘.
    텍스트에 명시되지 않은 정보는 억지로 지어내지 말고 "미정" 또는 "없음"으로 처리해
    모든 내용은 반드시 100% 한국어(Korean)로만 작성해라. 중국어나 일본어는 절대 사용 금지.

    [담당자 추출 규칙 - 매우 중요]
    회의록은 "이름: 발언내용" 형식으로 구성되어 있어.
    담당자를 결정할 때 아래 두 가지 패턴을 반드시 구분해:

    패턴 1 - 본인이 직접 선언하는 경우 → 발언한 화자가 담당자
      예) "김규호: 저는 발표 자료 만들겠습니다" → assignee: 김규호
      예) "류지우: 저는 STT 테스트 해볼게요" → assignee: 류지우

    패턴 2 - 리더가 다른 사람에게 지시하는 경우 → 지시받은 사람이 담당자
      예) "김지원: 규호님은 체크리스트 부탁드립니다" → assignee: 김규호

    [출력 형식]
    {{
      "cotent": "회의록 내용을 정리해줘. 줄바꿈은 \\n으로 표현하고 JSON 문자열 안에서 실제 줄바꿈 금지. 형식: 큰 주제\\n1. 세부 내용\\n  - 더 구체적인 내용.",
      "todo_list": [
        {{
          "title": "해당 담당자가 해야 할 업무 내용(태스크 명)",
          "content": "해당 담당자가 해야 할 구체적인 업무 내용",
          "owner": "담당자 이름",
          "due_date": "마감 일정(YYYY-MM-DD 형식)",
          "priority": "우선 순위(High, Medium, Low, Lowest 중 하나)"
        }}
      ]
    }}

    [회의록 텍스트]
    {meeting_text}
    """

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Always respond in valid JSON format only, with no extra text."},
        {"role": "user", "content": prompt},
    ]

    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )

    model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

    generated_ids = model.generate(
        **model_inputs,
        max_new_tokens=2048,
        do_sample=False,
        repetition_penalty=1.1,
    )

    generated_ids = [
        output_ids[len(input_ids):]
        for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
    ]
    response = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]

    # thinking 블록 제거
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

    # JSON 파싱
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    else:
        raise ValueError(f"JSON 파싱 실패: {response[:200]}")


# ── API 엔드포인트 ─────────────────────────────────────────────────────────
@app.get("/")
def health_check():
    return {"status": "ok", "message": "RunPod 서버 정상 동작 중"}


@app.post("/generate", response_model=GenerateResponse)
def generate_minutes(req: GenerateRequest):
    start = time.time()
    result = extract_minutes(req.text)
    elapsed = time.time() - start
    print(f"✅ 회의록 생성 완료 | {elapsed:.1f}초")
    return result
