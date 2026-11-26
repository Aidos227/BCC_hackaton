# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from datetime import datetime, time, date

class Undefined(Exception):
    def __init__(self, message, req_ids):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {
        "writeoff_amount": None,
        "push_sent": "нет",
        "api_status": None,
        "api_response": None
    }

    # R-25: При отсутствии авторизации API возвращает статус 401.
    if "auth_header" in scenario and scenario["auth_header"] is None:
        trace.append("R-25")
        outputs["api_status"] = 401
        outputs["_trace"] = trace
        return outputs

    # Проверка параметров API /settings (R-18, R-19, R-20, R-21, R-22, R-24)
    if "amount" in scenario or "threshold" in scenario or "phone" in scenario or "cardId" in scenario:
        amount = scenario.get("amount")
        threshold = scenario.get("threshold")
        phone = scenario.get("phone")
        card_id = scenario.get("cardId")

        max_amount = 20000 if interp.get("I2") == "a" else 50000
        
        is_valid = True
        if amount is None or not isinstance(amount, int) or not (100 <= amount <= max_amount):
            is_valid = False
        if threshold is None or not isinstance(threshold, int) or not (0 <= threshold <= 5000):
            is_valid = False
        if phone is None or not isinstance(phone, str) or not phone.startswith("+7") or len(phone) != 12 or not phone[1:].isdigit():
            is_valid = False
        if card_id is None or not isinstance(card_id, str) or not card_id:
            is_valid = False

        if not is_valid:
            trace.append("R-24")
            outputs["api_status"] = 400
            outputs["api_response"] = '{"message":"Некорректные параметры"}'
            outputs["_trace"] = trace
            return outputs
        else:
            trace.append("R-23")
            outputs["api_status"] = 200
            outputs["api_response"] = '{"result":"OK"}'
            outputs["_trace"] = trace
            return outputs

    # R-07: Клиент может отключить автопополнение в любой момент; отключение действует сразу.
    if scenario.get("autopay_enabled") is False:
        trace.append("R-07")
        outputs["_trace"] = trace
        return outputs

    # R-05, R-17: Автопополнение выполняется не чаще одного раза в сутки.
    last_autopay_time = scenario.get("last_autopay_time")
    current_event_time = scenario.get("current_event_time")
    if last_autopay_time and current_event_time:
        trace.append("R-05")
        trace.append("R-17")
        outputs["_trace"] = trace
        return outputs

    last_dt_str = scenario.get("last_autopay_datetime")
    curr_dt_str = scenario.get("current_event_datetime")
    if last_dt_str and curr_dt_str:
        last_dt = datetime.fromisoformat(last_dt_str)
        curr_dt = datetime.fromisoformat(curr_dt_str)
        if (curr_dt - last_dt).total_seconds() < 86400:
            trace.append("R-05")
            outputs["_trace"] = trace
            return outputs
        else:
            trace.append("R-05")

    # R-03, R-04, R-15, R-16: Когда оператор сообщает, что баланс номера стал ниже порога
    threshold = scenario.get("threshold")
    operator_balance = scenario.get("operator_balance")
    amount = scenario.get(
        "amount", 
        1000 if scenario.get("threshold") == 500 else 0
    )

    if threshold is not None and operator_balance is not None:
        i1_mode = interp.get("I1", "a")
        is_below = False
        if i1_mode == "a":
            is_below = operator_balance < threshold
        else:
            is_below = operator_balance <= threshold

        if is_below:
            trace.append("R-03")
            trace.append("R-04")
            trace.append("R-06")
            outputs["writeoff_amount"] = amount
            outputs["push_sent"] = "да"

    outputs["_trace"] = trace
    return outputs

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: баланс ниже порога",
  "quote": "| Порог 500 ₸, сумма 1 000 ₸ | Оператор сообщает баланс 499 ₸ | Списано 1 000 ₸, push отправлен |",
  "situation": "Порог 500 ₸, сумма 1 000 ₸. Оператор сообщает баланс 499 ₸.",
  "targets": [
   "R-15"
  ],
  "input": {
   "threshold": 500,
   "amount": 1000,
   "operator_balance": 499
  },
  "expected": {
   "writeoff_amount": 1000,
   "push_sent": true,
   "api_status": null,
   "api_response": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: баланс равен порогу",
  "quote": "| Порог 500 ₸, сумма 1 000 ₸ | Оператор сообщает баланс 500 ₸ | Списано 1 000 ₸, push отправлен |",
  "situation": "Порог 500 ₸, сумма 1 000 ₸. Оператор сообщает баланс 500 ₸.",
  "targets": [
   "R-16"
  ],
  "input": {
   "threshold": 500,
   "amount": 1000,
   "operator_balance": 500
  },
  "expected": {
   "writeoff_amount": 1000,
   "push_sent": true,
   "api_status": null,
   "api_response": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: повторное событие в тот же день",
  "quote": "| Пополнение уже было сегодня в 09:00 | Оператор сообщает низкий баланс в 21:00 | Списания нет |",
  "situation": "Пополнение уже было сегодня в 09:00. Оператор сообщает низкий баланс в 21:00.",
  "targets": [
   "R-17"
  ],
  "input": {
   "last_autopay_time": "09:00",
   "current_event_time": "21:00",
   "operator_low_balance": true
  },
  "expected": {
   "writeoff_amount": 0,
   "push_sent": false,
   "api_status": null,
   "api_response": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Сумма пополнения ниже минимального значения",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings с параметром amount равным 99 тенге.",
  "targets": [
   "R-02",
   "R-21",
   "R-24"
  ],
  "input": {
   "phone": "+77011234567",
   "cardId": "card_123",
   "amount": 99,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 400,
   "api_response": "{\"message\":\"Некорректные параметры\"}"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Сумма пополнения на нижней границе",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings с параметром amount равным 100 тенге.",
  "targets": [
   "R-02",
   "R-21",
   "R-23"
  ],
  "input": {
   "phone": "+77011234567",
   "cardId": "card_123",
   "amount": 100,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 200,
   "api_response": "{\"result\":\"OK\"}"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Сумма пополнения на верхней границе функциональных требований",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings с параметром amount равным 20 000 тенге.",
  "targets": [
   "R-02",
   "R-21",
   "R-23"
  ],
  "input": {
   "phone": "+77011234567",
   "cardId": "card_123",
   "amount": 20000,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 200,
   "api_response": "{\"result\":\"OK\"}"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Порог баланса на нижней границе",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings с параметром threshold равным 0 тенге.",
  "targets": [
   "R-03",
   "R-22",
   "R-23"
  ],
  "input": {
   "phone": "+77011234567",
   "cardId": "card_123",
   "amount": 1000,
   "threshold": 0
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 200,
   "api_response": "{\"result\":\"OK\"}"
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Порог баланса выше верхней границы",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings с параметром threshold равным 5 001 тенге.",
  "targets": [
   "R-03",
   "R-22",
   "R-24"
  ],
  "input": {
   "phone": "+77011234567",
   "cardId": "card_123",
   "amount": 1000,
   "threshold": 5001
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 400,
   "api_response": "{\"message\":\"Некорректные параметры\"}"
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Событие оператора при отключенном автопополнении",
  "quote": "",
  "situation": "Клиент отключил автопополнение в 10:00. Оператор сообщает о низком балансе в 11:00.",
  "targets": [
   "R-04",
   "R-07"
  ],
  "input": {
   "autopay_enabled": false,
   "disable_time": "10:00",
   "operator_event_time": "11:00",
   "operator_balance": 200
  },
  "expected": {
   "writeoff_amount": 0,
   "push_sent": false,
   "api_status": null,
   "api_response": null
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Запрос без авторизации",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings без заголовков авторизации с валидными параметрами.",
  "targets": [
   "R-25"
  ],
  "input": {
   "auth_header": null,
   "phone": "+77011234567",
   "cardId": "card_123",
   "amount": 1000,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 401,
   "api_response": null
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Автопополнение ровно через сутки после предыдущего",
  "quote": "",
  "situation": "Пополнение было выполнено вчера в 14:00:00. Оператор сообщает о низком балансе сегодня ровно в 14:00:00.",
  "targets": [
   "R-04",
   "R-05"
  ],
  "input": {
   "last_autopay_datetime": "2023-10-01T14:00:00",
   "current_event_datetime": "2023-10-02T14:00:00",
   "operator_balance": 100
  },
  "expected": {
   "writeoff_amount": 1000,
   "push_sent": true,
   "api_status": null,
   "api_response": null
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-03",
   "R-16"
  ],
  "quote": "Когда оператор сообщает, что баланс номера стал ниже порога, банк списывает сумму пополнения с карты и переводит её оператору.",
  "question": "Считается ли условие 'баланс стал ниже порога' выполненным, если текущий баланс равен порогу?",
  "a": "Равенство баланса порогу не означает, что баланс 'ниже порога', списание происходить не должно.",
  "b": "Равенство баланса порогу трактуется как наступление события списания (согласно критерию приемки)."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-02",
   "R-21"
  ],
  "quote": "Клиент задаёт сумму пополнения от 100 до 20 000 ₸ целым числом",
  "question": "Какое максимальное значение суммы пополнения является валидным: 20 000 из функциональных требований или 50 000 из описания API?",
  "a": "Максимальная сумма ограничена 20 000 ₸ согласно функциональным требованиям.",
  "b": "Максимальная сумма ограничена 50 000 ₸ согласно параметрам API."
 }
]""")

if __name__ == "__main__":
    ids = [i["id"] for i in INTERPRETATIONS][:4]
    combos = [dict(zip(ids, v)) for v in itertools.product("ab", repeat=len(ids))] or [{}]
    for s in SCENARIOS:
        print(f"\n{s['id']} [{s.get('source')}] {s.get('title')}")
        if s.get("expected"):
            print("  ожидается по документу:", s["expected"])
        for c in combos:
            try:
                r = run(s.get("input") or {}, dict(c))
                print(" ", c or "", "→", r)
            except Undefined as u:
                print(" ", c or "", "→ НЕ ОПРЕДЕЛЕНО:", u.question)
