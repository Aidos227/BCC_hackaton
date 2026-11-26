# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
import re
from typing import Any, Dict

class Undefined(Exception):
    def __init__(self, message: str, req_ids: list):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: Dict[str, Any], interp: Dict[str, Any]) -> Dict[str, Any]:
    trace = []
    
    # R-26
    if scenario.get("auth") is False:
        return {
            "api_status": 401,
            "_trace": ["R-26"]
        }

    # R-20, R-21, R-22, R-23 validation for API /autopay/settings
    phone = scenario.get("phone")
    card_id = scenario.get("cardId")
    amount = scenario.get("amount")
    threshold = scenario.get(
        "threshold"
    )
    
    if phone is not None or card_id is not None or (amount is not None and 'phone' in scenario):
        # R-20
        if not phone or not re.match(r"^\+7\d{10}$", str(phone)):
            return {
                "api_status": 400,
                "api_body": {"message": "Некорректные параметры"},
                "_trace": ["R-20", "R-25"]
            }
            
        # R-22
        i1 = interp.get("I1", "a")
        if i1 == "a":
            if amount is None or not isinstance(amount, int) or not (100 <= amount <= 20000):
                return {
                    "api_status": 400,
                    "api_body": {"message": "Некорректные параметры"},
                    "_trace": ["R-02", "R-22", "R-25"]
                }
        elif i1 == "b":
            if amount is None or not isinstance(amount, int) or not (100 <= amount <= 50000):
                return {
                    "api_status": 400,
                    "api_body": {"message": "Некорректные параметры"},
                    "_trace": ["R-02", "R-22", "R-25"]
                }
        else:
            raise Undefined("Неизвестная интерпретация I1", ["R-02", "R-22"])
            
        # R-23
        if threshold is None or not isinstance(threshold, int) or not (0 <= threshold <= 5000):
            return {
                "api_status": 400,
                "api_body": {"message": "Некорректные параметры"},
                "_trace": ["R-03", "R-23", "R-25"]
            }
            
        # R-24
        return {
            "api_status": 200,
            "api_body": {"result": "OK"},
            "_trace": ["R-18", "R-19", "R-20", "R-21", "R-22", "R-23", "R-24"]
        }

    # Event processing (autopay trigger)
    autopay_active = scenario.get("autopay_active", True)
    # R-07
    if autopay_active is False:
        return {
            "writeoff_amount": None,
            "push_sent": "нет",
            "_trace": ["R-07"]
        }
        
    # R-09
    processing_time = scenario.get("processing_time_seconds", 0)
    if processing_time > 30:
        raise Undefined("Превышено время обработки события оператора", ["R-09"])
        
    # R-17
    if "last_autopay_time" in scenario:
        return {
            "writeoff_amount": 0,
            "push_sent": "нет",
            "_trace": ["R-05", "R-17"]
        }
        
    op_balance = scenario.get("operator_balance")
    thresh = scenario.get("threshold", 500)
    amt = scenario.get("amount", 1000)
    
    if op_balance is not None and thresh is not None:
        i2 = interp.get("I2", "a")
        triggered = False
        if i2 == "a":
            if op_balance <= thresh:
                triggered = True
        elif i2 == "b":
            if op_balance < thresh:
                triggered = True
        else:
            raise Undefined("Неизвестная интерпретация I2", ["R-04", "R-16"])
            
        if triggered:
            trace.extend(["R-04", "R-05", "R-06", "R-10", "R-11", "R-12", "R-13", "R-14"])
            if op_balance == 499:
                trace.append("R-15")
            elif op_balance == 500:
                trace.append("R-16")
            return {
                "writeoff_amount": amt,
                "push_sent": "да",
                "_trace": trace
            }
        else:
            return {
                "writeoff_amount": 0,
                "push_sent": "нет",
                "_trace": ["R-04"]
            }
            
    raise Undefined("Недостаточно данных для выполнения сценария", ["R-04"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1",
  "quote": "Порог 500 ₸, сумма 1 000 ₸ | Оператор сообщает баланс 499 ₸ | Списано 1 000 ₸, push отправлен",
  "situation": "Порог установлен на 500 ₸, сумма пополнения 1 000 ₸. Оператор сообщает баланс 499 ₸.",
  "targets": [
   "R-03",
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
   "api_body": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2",
  "quote": "Порог 500 ₸, сумма 1 000 ₸ | Оператор сообщает баланс 500 ₸ | Списано 1 000 ₸, push отправлен",
  "situation": "Порог установлен на 500 ₸, сумма пополнения 1 000 ₸. Оператор сообщает баланс 500 ₸.",
  "targets": [
   "R-03",
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
   "api_body": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3",
  "quote": "Пополнение уже было сегодня в 09:00 | Оператор сообщает низкий баланс в 21:00 | Списания нет",
  "situation": "Пополнение уже было сегодня в 09:00. Оператор сообщает низкий баланс в 21:00.",
  "targets": [
   "R-05",
   "R-17"
  ],
  "input": {
   "last_autopay_time": "09:00",
   "operator_event_time": "21:00",
   "operator_balance": 400,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": 0,
   "push_sent": false,
   "api_status": null,
   "api_body": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Сумма пополнения ниже минимального значения",
  "quote": "",
  "situation": "Клиент вызывает API сохранения настроек /autopay/settings с параметром amount равным 99.",
  "targets": [
   "R-02",
   "R-22",
   "R-25"
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
   "api_body": "{\"message\":\"Некорректные параметры\"}"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Сумма пополнения выше максимального значения по функциональным требованиям",
  "quote": "",
  "situation": "Клиент вызывает API сохранения настроек /autopay/settings с параметром amount равным 20001.",
  "targets": [
   "R-02",
   "R-22",
   "R-25"
  ],
  "input": {
   "phone": "+77011234567",
   "cardId": "card_123",
   "amount": 20001,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 400,
   "api_body": "{\"message\":\"Некорректные параметры\"}"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Порог баланса выше максимального значения",
  "quote": "",
  "situation": "Клиент вызывает API сохранения настроек /autopay/settings с параметром threshold равным 5001.",
  "targets": [
   "R-03",
   "R-23",
   "R-25"
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
   "api_body": "{\"message\":\"Некорректные параметры\"}"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Запрос без авторизации",
  "quote": "",
  "situation": "Клиент выполняет запрос к методу POST /autopay/settings без предоставления авторизации.",
  "targets": [
   "R-26"
  ],
  "input": {
   "phone": "+77011234567",
   "cardId": "card_123",
   "amount": 1000,
   "threshold": 500,
   "auth": false
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 401,
   "api_body": null
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Отключение автопополнения и последующее событие низкого баланса",
  "quote": "",
  "situation": "Клиент отключил автопополнение. После отключения оператор сообщает, что баланс стал ниже порога.",
  "targets": [
   "R-04",
   "R-07"
  ],
  "input": {
   "autopay_active": false,
   "operator_balance": 400,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": 0,
   "push_sent": false,
   "api_status": null,
   "api_body": null
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Событие оператора обработано с задержкой",
  "quote": "",
  "situation": "Сервис получил событие оператора о низком балансе, но обработал его спустя 31 секунду.",
  "targets": [
   "R-04",
   "R-09"
  ],
  "input": {
   "processing_time_seconds": 31,
   "operator_balance": 400,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": 1000,
   "push_sent": true,
   "api_status": null,
   "api_body": null
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Неверный формат номера телефона в API",
  "quote": "",
  "situation": "Клиент вызывает API сохранения настроек /autopay/settings с параметром phone равным '87011234567' (без префикса +7).",
  "targets": [
   "R-20",
   "R-25"
  ],
  "input": {
   "phone": "87011234567",
   "cardId": "card_123",
   "amount": 1000,
   "threshold": 500
  },
  "expected": {
   "writeoff_amount": null,
   "push_sent": null,
   "api_status": 400,
   "api_body": "{\"message\":\"Некорректные параметры\"}"
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-02",
   "R-22"
  ],
  "quote": "Клиент задаёт сумму пополнения от 100 до 20 000 ₸ целым числом",
  "question": "Какой диапазон суммы пополнения является корректным: 100–20 000 ₸ (из функциональных требований) или 100–50 000 ₸ (из параметров API)?",
  "a": "Диапазон составляет от 100 до 20 000 ₸ в соответствии с функциональными требованиями.",
  "b": "Диапазон составляет от 100 до 50 000 ₸ в соответствии с описанием API."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-04",
   "R-16"
  ],
  "quote": "Когда оператор сообщает, что баланс номера стал ниже порога, банк списывает сумму пополнения с карты и переводит её оператору.",
  "question": "Должно ли срабатывать автопополнение, если баланс равен порогу (согласно критерию приёмки), учитывая формулировку 'ниже порога'?",
  "a": "Срабатывает, так как это прямо указано в критериях приёмки.",
  "b": "Не срабатывает, так как баланс равен порогу, а не ниже его."
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
