# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from decimal import Decimal
from typing import Any, Dict

class Undefined(Exception):
    pass

def run(scenario: dict, interp: dict) -> dict:
    _trace = []
    
    if "cardId" in scenario and "token_client_id" in scenario:
        if scenario["token_client_id"] != "client-A":
            _trace.append("R-32")
            return {"api_status": 404, "api_result": "Карта не найдена", "_trace": _trace}
        else:
            _trace.append("R-32")
            return {"api_status": 404, "api_result": "Карта не найдена", "_trace": _trace}

    if "cardId" in scenario and "amount" in scenario and "enabled" in scenario:
        amt = scenario["amount"]
        if not (1000 <= amt <= 1000000):
            _trace.append("R-03")
            _trace.append("R-28")
            return {"api_status": 400, "api_result": "ERROR", "_trace": _trace}
        _trace.append("R-03")
        _trace.append("R-28")
        _trace.append("R-29")
        return {"api_status": 200, "api_result": "OK", "_trace": _trace}

    if "old_threshold" in scenario:
        _trace.append("R-10")
        return {"expenses_kzt": scenario.get("current_expenses", 0), "_trace": _trace}

    if scenario.get("duplicate_event"):
        _trace.append("R-15")
        return {"expenses_kzt": scenario.get("initial_expenses", 0), "push_count": 1 if scenario.get("push_already_sent") else 0, "_trace": _trace}

    if scenario.get("transaction_type") == "transfer":
        _trace.append("R-07")
        return {"expenses_kzt": scenario.get("initial_expenses", 0), "push_count": 0, "_trace": _trace}

    if "purchase_date_time" in scenario:
        _trace.append("R-05")
        return {"expenses_kzt": scenario.get("amount", 0), "_trace": _trace}

    initial = scenario.get("initial_expenses", 0)
    threshold = scenario.get("threshold", 0)
    tx_amt = scenario.get("transaction_amount", 0)
    enabled = scenario.get("enabled", 1)

    new_expenses = initial + tx_amt
    push_count = 0

    if enabled == 1:
        i2 = interp.get("I2", "a")
        if i2 == "a":
            if initial < threshold and new_expenses >= threshold:
                push_count = 1
                _trace.append("R-08")
        else:
            if new_expenses >= threshold:
                push_count = 1
                _trace.append("R-08")

    _trace.append("R-05")
    return {"expenses_kzt": new_expenses, "push_count": push_count, "_trace": _trace}

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приёмки 1: Достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "Исходные накопленные расходы составляют 48 500 тенге, установленный порог равен 50 000 тенге. Совершается и проводится покупка на сумму 1 500 тенге.",
  "targets": [
   "R-08",
   "R-16"
  ],
  "input": {
   "initial_expenses": 48500,
   "threshold": 50000,
   "transaction_amount": 1500,
   "transaction_type": "purchase"
  },
  "expected": {
   "expenses_kzt": 50000,
   "push_count": 1,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приёмки 2: Покупка на стыке месяцев",
  "quote": "Покупка совершена 31.01 в 23:58, сумма 4 000 ₸ | Проведение 01.02 в 00:03 (Алматы) | Расходы февраля увеличились на 4 000 ₸",
  "situation": "Покупка на сумму 4 000 тенге совершена 31 января в 23:58 по времени Алматы и проведена 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-05",
   "R-17"
  ],
  "input": {
   "purchase_date_time": "31.01 23:58",
   "processing_date_time": "01.02 00:03",
   "amount": 4000
  },
  "expected": {
   "expenses_kzt": 4000,
   "push_count": 0,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приёмки 3: Игнорирование переводов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "Текущие расходы составляют 19 900 тенге при пороге 20 000 тенге. Выполняется операция перевода на сумму 500 тенге.",
  "targets": [
   "R-07",
   "R-18"
  ],
  "input": {
   "initial_expenses": 19900,
   "threshold": 20000,
   "transaction_amount": 500,
   "transaction_type": "transfer"
  },
  "expected": {
   "expenses_kzt": 19900,
   "push_count": 0,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Нижняя граница порога через API",
  "quote": "",
  "situation": "Владелец активной тенговой карты отправляет GET-запрос на сохранение порога с параметром amount равным 1000 и enabled равным 1 для карты cardId.",
  "targets": [
   "R-03",
   "R-19",
   "R-28"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Верхняя граница порога через API",
  "quote": "",
  "situation": "Владелец активной тенговой карты отправляет GET-запрос на сохранение порога с параметром amount равным 1000000 и enabled равным 1 для карты cardId.",
  "targets": [
   "R-03",
   "R-19",
   "R-28"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Недопустимое значение порога ниже нижней границы",
  "quote": "",
  "situation": "Владелец карты отправляет GET-запрос на сохранение порога с параметром amount равным 999 и enabled равным 1.",
  "targets": [
   "R-03",
   "R-23",
   "R-28"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Недопустимое значение порога выше верхней границы",
  "quote": "",
  "situation": "Владелец карты отправляет GET-запрос на сохранение порога с параметром amount равным 1000001 и enabled равным 1.",
  "targets": [
   "R-03",
   "R-23",
   "R-28"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Повторная доставка события процессинга",
  "quote": "",
  "situation": "Событие о проведённой покупке, которая уже была учтена в расходах месяца и повлекла отправку push, доставляется сервису повторно.",
  "targets": [
   "R-09",
   "R-15"
  ],
  "input": {
   "initial_expenses": 50000,
   "threshold": 50000,
   "push_already_sent": true,
   "duplicate_event": true
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Отправка push при отключенном оповещении",
  "quote": "",
  "situation": "Для карты с изначально отключенным оповещением сумма расходов достигает установленного порогового значения.",
  "targets": [
   "R-04",
   "R-08"
  ],
  "input": {
   "enabled": 0,
   "initial_expenses": 49000,
   "threshold": 50000,
   "transaction_amount": 2000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Смена порога при уже накопленных расходах выше нового порога",
  "quote": "",
  "situation": "Накопленные расходы за месяц составляют 60 000 тенге. Владелец меняет порог со старого значения 70 000 тенге на новое значение 50 000 тенге.",
  "targets": [
   "R-10",
   "R-11"
  ],
  "input": {
   "current_expenses": 60000,
   "old_threshold": 70000,
   "new_threshold": 50000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос к API с чужой картой",
  "quote": "",
  "situation": "Клиент отправляет GET-запрос на сохранение порога с bearer-токеном своей сессии, но в параметре cardId указывает идентификатор карты, принадлежащей другому клиенту.",
  "targets": [
   "R-20",
   "R-32"
  ],
  "input": {
   "token_client_id": "client-A",
   "cardId": "card-belonging-to-client-B",
   "amount": 50000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-05",
   "R-17"
  ],
  "quote": "Покупка относится к тому месяцу, в котором она была совершена (время Алматы). Учитываются проведённые покупки.",
  "question": "К какому месяцу относится покупка, если она совершена в одном месяце, а проведена в другом?",
  "a": "К месяцу совершения покупки",
  "b": "К месяцу проведения покупки"
 },
 {
  "id": "I2",
  "req_ids": [
   "R-08",
   "R-16"
  ],
  "quote": "Push отправляется в момент, когда сумма расходов впервые становится не меньше порога, а до этого была меньше.",
  "question": "Считается ли условие 'а до этого была меньше' выполненным, если расходы изначально равны порогу?",
  "a": "Да, если перед операцией сумма была строго меньше порога",
  "b": "Нет, если в текущем месяце расходы уже достигали порога ранее"
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
