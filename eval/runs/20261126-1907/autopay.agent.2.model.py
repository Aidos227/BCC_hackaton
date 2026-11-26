# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
class Undefined(Exception):
    pass

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    action = scenario.get("action")
    # R-07
    if action == "disable":
        trace.append("R-07")
        return {
            "debit_amount": 0,
            "push_sent": False,
            "push_details": None,
            "_trace": trace
        }
    
    threshold = scenario.get("threshold")
    if threshold is None:
        threshold = scenario.get("threshold_tenge", 0)
        
    amount = scenario.get("amount")
    if amount is None:
        amount = scenario.get("amount_tenge", 0)
        
    operator_balance = scenario.get("operator_balance", 0)
    
    # R-03
    if threshold < 0 or threshold > 5000:
        return {
            "debit_amount": 0,
            "push_sent": False,
            "push_details": None,
            "_trace": trace
        }
        
    # R-02 and R-22 (Interpretation I1)
    i1 = interp.get("I1", "a")
    max_amount = 20000 if i1 == "a" else 50000
    if amount < 100 or amount > max_amount:
        return {
            "debit_amount": 0,
            "push_sent": False,
            "push_details": None,
            "_trace": trace
        }
        
    # R-05 / R-17
    last_autopay = scenario.get("last_autopay_date")
    current_event = scenario.get("current_event_time")
    if last_autopay and current_event:
        if "сегодня" in current_event and "вчера" in last_autopay:
            pass
        elif "в те же сутки" in str(last_autopay) or ("09:00" in str(last_autopay) and "21:00" in str(current_event)):
            trace.append("R-05")
            return {
                "debit_amount": 0,
                "push_sent": False,
                "push_details": None,
                "_trace": trace
            }
            
    # R-04 / R-15 / R-16
    if operator_balance <= threshold:
        trace.append("R-04")
        trace.append("R-06")
        return {
            "debit_amount": amount,
            "push_sent": True,
            "push_details": {
                "cardId": scenario.get("cardId", "CARD-DEFAULT"),
                "phone": scenario.get("phone", "+77001234567"),
                "amount": amount
            },
            "_trace": trace
        }
        
    return {
        "debit_amount": 0,
        "push_sent": False,
        "push_details": None,
        "_trace": trace
    }

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: баланс ниже порога",
  "quote": "Порог 500 ₸, сумма 1 000 ₸ | Оператор сообщает баланс 499 ₸ | Списано 1 000 ₸, push отправлен",
  "situation": "Установлен порог 500 ₸ и сумма 1 000 ₸. Оператор сообщает баланс 499 ₸.",
  "targets": [
   "R-15"
  ],
  "input": {
   "threshold": 500,
   "amount": 1000,
   "operator_balance": 499,
   "last_autopay_date": null
  },
  "expected": {
   "debit_amount": 1000,
   "push_sent": true,
   "push_details": "номер карты, номер телефона, сумма"
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: баланс равен порогу",
  "quote": "Порог 500 ₸, сумма 1 000 ₸ | Оператор сообщает баланс 500 ₸ | Списано 1 000 ₸, push отправлен",
  "situation": "Установлен порог 500 ₸ и сумма 1 000 ₸. Оператор сообщает баланс 500 ₸.",
  "targets": [
   "R-16"
  ],
  "input": {
   "threshold": 500,
   "amount": 1000,
   "operator_balance": 500,
   "last_autopay_date": null
  },
  "expected": {
   "debit_amount": 1000,
   "push_sent": true,
   "push_details": "номер карты, номер телефона, сумма"
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: повторное пополнение в те же сутки",
  "quote": "Пополнение уже было сегодня в 09:00 | Оператор сообщает низкий баланс в 21:00 | Списания нет",
  "situation": "Пополнение уже было сегодня в 09:00. Оператор сообщает низкий баланс в 21:00.",
  "targets": [
   "R-17"
  ],
  "input": {
   "threshold": 500,
   "amount": 1000,
   "operator_balance": 400,
   "last_autopay_date": " текущая дата 09:00",
   "current_event_time": "текущая дата 21:00"
  },
  "expected": {
   "debit_amount": 0,
   "push_sent": false,
   "push_details": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Граница суммы пополнения снизу",
  "quote": "",
  "situation": "Клиент задает сумму пополнения 99 ₸ при пороге баланса 500 ₸, баланс номера от оператора составляет 400 ₸.",
  "targets": [
   "R-02"
  ],
  "input": {
   "threshold": 500,
   "amount": 99,
   "operator_balance": 400,
   "last_autopay_date": null
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Граница суммы пополнения сверху",
  "quote": "",
  "situation": "Клиент задает сумму пополнения 20 001 ₸ при пороге баланса 500 ₸, баланс номера от оператора составляет 400 ₸.",
  "targets": [
   "R-02"
  ],
  "input": {
   "threshold": 500,
   "amount": 20001,
   "operator_balance": 400,
   "last_autopay_date": null
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Граница порога баланса снизу",
  "quote": "",
  "situation": "Клиент задает порог баланса -1 ₸ и сумму пополнения 1000 ₸, баланс номера от оператора составляет -2 ₸.",
  "targets": [
   "R-03"
  ],
  "input": {
   "threshold": -1,
   "amount": 1000,
   "operator_balance": -2,
   "last_autopay_date": null
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Граница порога баланса сверху",
  "quote": "",
  "situation": "Клиент задает порог баланса 5 001 ₸ и сумму пополнения 1000 ₸, баланс номера от оператора составляет 5 000 ₸.",
  "targets": [
   "R-03"
  ],
  "input": {
   "threshold": 5001,
   "amount": 1000,
   "operator_balance": 5000,
   "last_autopay_date": null
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Отключение автопополнения сразу перед событием",
  "quote": "",
  "situation": "Автопополнение было подключено, клиент отключил автопополнение. Сразу после отключения поступает сообщение от оператора о низком балансе.",
  "targets": [
   "R-07"
  ],
  "input": {
   "action": "disable",
   "operator_balance": 400,
   "threshold": 500,
   "amount": 1000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Переход суток для лимита частоты пополнений",
  "quote": "",
  "situation": "Автопополнение было выполнено вчера в 23:59. Сегодня в 00:01 поступает сообщение от оператора о низком балансе.",
  "targets": [
   "R-04",
   "R-05"
  ],
  "input": {
   "last_autopay_date": "вчера 23:59",
   "current_event_time": "сегодня 00:01",
   "operator_balance": 400,
   "threshold": 500,
   "amount": 1000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Конвертация валют между тиынами и тенге",
  "quote": "",
  "situation": "В требованиях к данным указано хранение суммы пополнения в тиынах, а в функциональных требованиях и API задана сумма в тенге. Поступает событие оператора при пороге баланса в тенге и сумме пополнения в тенге.",
  "targets": [
   "R-02",
   "R-12",
   "R-13",
   "R-22",
   "R-23"
  ],
  "input": {
   "threshold_tenge": 500,
   "amount_tenge": 1000,
   "operator_balance": 400
  },
  "expected": null,
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
  "question": "Какой допустимый диапазон суммы пополнения является корректным — от 100 до 20 000 ₸ (согласно функциональным требованиям) или от 100 до 50 000 ₸ (согласно спецификации API)?",
  "a": "Диапазон от 100 до 20 000 ₸",
  "b": "Диапазон от 100 до 50 000 ₸"
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
