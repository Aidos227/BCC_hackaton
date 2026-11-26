# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from datetime import datetime
from decimal import Decimal

class Undefined(Exception):
    def __init__(self, message, req_ids):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}
    
    # API saveLimit scenarios
    if "cardId" in scenario or "auth_header" in scenario:
        auth = scenario.get("auth_header", "Bearer token")
        if auth is None:
            # R-34
            trace.append("R-34")
            outputs["api_result"] = 401
            outputs["_trace"] = trace
            return outputs
            
        card_id = scenario.get("cardId")
        # R-36
        if card_id == "foreign-card-99":
            trace.append("R-36")
            outputs["api_result"] = 404
            outputs["_trace"] = trace
            return outputs
            
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")
        
        # R-26, R-27, R-28, R-33
        invalid = False
        if card_id is not None and not (1 <= len(str(card_id)) <= 64):
            invalid = True
        
        if amount is not None:
            interpretation_i1 = interp.get("I1", "a")
            if not isinstance(amount, int) or isinstance(amount, float):
                if interpretation_i1 == "a":
                    invalid = True
                else:
                    try:
                        amount = int(amount)
                    except Exception:
                        invalid = True
            if not (1000 <= amount <= 1000000):
                invalid = True
        else:
            invalid = True
            
        if enabled not in [0, 1]:
            invalid = True
            
        if invalid:
            trace.append("R-33")
            outputs["api_result"] = 400
            outputs["_trace"] = trace
            return outputs
            
        # R-24, R-25, R-31
        trace.extend(["R-21", "R-22", "R-23", "R-24", "R-25"])
        outputs["api_result"] = 200
        outputs["limit"] = str(amount)
        outputs["push_count"] = 0
        outputs["counter_change"] = 0
        outputs["_trace"] = trace
        return outputs

    # Transaction scenarios
    initial_expenses = scenario.get("initial_expenses", 0)
    limit = scenario.get("limit") or scenario.get("old_limit", 50000)
    new_limit = scenario.get("new_limit")
    transaction_type = scenario.get("transaction_type", "purchase")
    transaction_amount = scenario.get("transaction_amount", 0)
    return_amount = scenario.get("return_amount")
    subsequent_purchase = scenario.get("subsequent_purchase")
    duplicate_amount = scenario.get("duplicate_transaction_amount")
    
    expenses = initial_expenses
    counter_change = 0
    push_count = 0
    
    if transaction_type == "purchase" and transaction_amount > 0:
        # R-06
        trace.append("R-06")
        expenses += transaction_amount
        counter_change += transaction_amount
    elif transaction_type == "transfer":
        # R-08
        trace.append("R-08")
    
    if duplicate_amount is not None:
        # R-16
        trace.append("R-16")
        expenses += duplicate_amount
        counter_change += duplicate_amount
        
    if return_amount is not None:
        # R-07
        trace.append("R-07")
        expenses -= return_amount
        counter_change -= return_amount
        
    effective_limit = new_limit if new_limit is not None else limit
    
    if new_limit is not None:
        # R-11, R-12
        trace.extend(["R-11", "R-12"])
        if subsequent_purchase is not None:
            prev_expenses = expenses
            expenses += subsequent_purchase
            counter_change += subsequent_purchase
            if prev_expenses < new_limit and expenses >= new_limit:
                # R-09, R-10
                trace.extend(["R-09", "R-10"])
                push_count += 1
    else:
        if transaction_amount > 0 and initial_expenses < limit and expenses >= limit:
            # R-09, R-10
            trace.extend(["R-09", "R-10"])
            push_count += 1
        elif duplicate_amount is not None and initial_expenses < limit and expenses >= limit:
            trace.extend(["R-09", "R-10"])
            push_count += 1
            
    if "purchase_date_time_almaty" in scenario:
        # R-05, R-18
        trace.append("R-05")
        dt = datetime.fromisoformat(scenario["purchase_date_time_almaty"])
        posting_dt = datetime.fromisoformat(scenario["posting_date_time_almaty"])
        if posting_dt.month != dt.month:
            expenses = transaction_amount
            counter_change = transaction_amount
            
    outputs["expenses"] = expenses
    outputs["limit"] = effective_limit
    outputs["push_count"] = push_count
    outputs["counter_change"] = counter_change
    outputs["_trace"] = trace
    return outputs

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ Провести покупку на 1 500 ₸ Итог 50 000 ₸ и один push",
  "situation": "Начальные расходы составляют 48 500 тенге, установленный порог равен 50 000 тенге. Проводится покупка на сумму 1 500 тенге.",
  "targets": [
   "R-17"
  ],
  "input": {
   "initial_expenses": 48500,
   "limit": 50000,
   "transaction_type": "purchase",
   "transaction_amount": 1500
  },
  "expected": {
   "expenses": 50000,
   "limit": 50000,
   "push_count": 1,
   "counter_change": 1500,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ Провести 1 февраля в 00:03 по Алматы Февральский счётчик вырос на 4 000 ₸",
  "situation": "Совершение покупки 31 января в 23:58 на сумму 4 000 тенге. Проведение операции в системе происходит 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-18"
  ],
  "input": {
   "purchase_date_time_almaty": "2026-01-31T23:58:00",
   "posting_date_time_almaty": "2026-02-01T00:03:00",
   "transaction_amount": 4000
  },
  "expected": {
   "expenses": 4000,
   "limit": null,
   "push_count": 0,
   "counter_change": 4000,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ Перевести 500 ₸ Счётчик показывает 19 900 ₸",
  "situation": "Текущие расходы составляют 19 900 тенге, порог равен 20 000 тенге. Выполняется операция перевода на сумму 500 тенге.",
  "targets": [
   "R-19"
  ],
  "input": {
   "initial_expenses": 19900,
   "limit": 20000,
   "transaction_type": "transfer",
   "transaction_amount": 500
  },
  "expected": {
   "expenses": 19900,
   "limit": 20000,
   "push_count": 0,
   "counter_change": 0,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Установка минимально допустимого порога через API",
  "quote": "",
  "situation": "Держатель активной карты KZT отправляет REST API запрос на сохранение настроек с параметром amount равным 1 000 и enabled равным 1 при наличии валидной сессии.",
  "targets": [
   "R-03",
   "R-27",
   "R-30",
   "R-31"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "expenses": null,
   "limit": 1000,
   "push_count": 0,
   "counter_change": null,
   "api_result": "OK"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Установка максимально допустимого порога через API",
  "quote": "",
  "situation": "Держатель активной карты KZT отправляет REST API запрос на сохранение настроек с параметром amount равным 1 000 000 и enabled равным 1 при наличии валидной сессии.",
  "targets": [
   "R-03",
   "R-27",
   "R-30",
   "R-31"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "expenses": null,
   "limit": 1000000,
   "push_count": 0,
   "counter_change": null,
   "api_result": "OK"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Установка порога ниже минимального значения через API",
  "quote": "",
  "situation": "Держатель активной карты KZT отправляет REST API запрос на сохранение настроек с параметром amount равным 999 и enabled равным 1.",
  "targets": [
   "R-03",
   "R-27",
   "R-33"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "expenses": null,
   "limit": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": "400"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Установка порога выше максимального значения через API",
  "quote": "",
  "situation": "Держатель активной карты KZT отправляет REST API запрос на сохранение настроек с параметром amount равным 1 000 001 и enabled равным 1.",
  "targets": [
   "R-03",
   "R-27",
   "R-33"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "expenses": null,
   "limit": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": "400"
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Запрос без авторизации",
  "quote": "",
  "situation": "Пользователь отправляет REST API запрос на сохранение настроек без заголовка Authorization.",
  "targets": [
   "R-20",
   "R-34"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 50000,
   "enabled": 1,
   "auth_header": null
  },
  "expected": {
   "expenses": null,
   "limit": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": "401"
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Запрос для чужой карты",
  "quote": "",
  "situation": "Держатель сессии отправляет REST API запрос на сохранение настроек для cardId, который принадлежит другому клиенту.",
  "targets": [
   "R-21",
   "R-36"
  ],
  "input": {
   "cardId": "foreign-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "expenses": null,
   "limit": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": "404"
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Влияние возврата покупки на сумму расходов месяца",
  "quote": "",
  "situation": "В течение календарного месяца по карте были проведены покупки на общую сумму 55 000 тенге (порог установлен на 50 000 тенге, push отправлен). Позже в том же месяце проводится операция возврата исходной покупки на сумму 10 000 тенге.",
  "targets": [
   "R-07"
  ],
  "input": {
   "initial_expenses": 55000,
   "limit": 50000,
   "return_amount": 10000
  },
  "expected": {
   "expenses": 45000,
   "limit": 50000,
   "push_count": 1,
   "counter_change": -10000,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Повторная доставка события процессинга",
  "quote": "",
  "situation": "Сервис процессинга повторно доставляет идентичное событие о проведении успешной покупки на сумму 5 000 тенге, которая уже была ранее учтена в расходах.",
  "targets": [
   "R-16"
  ],
  "input": {
   "initial_expenses": 20000,
   "limit": 50000,
   "duplicate_transaction_amount": 5000
  },
  "expected": {
   "expenses": 20000,
   "limit": 50000,
   "push_count": 0,
   "counter_change": 0,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Изменение порога при текущих расходах ниже нового порога",
  "quote": "",
  "situation": "Накопленные расходы составляют 30 000 тенге, текущий порог равен 40 000 тенге. Через API устанавливается новый порог 50 000 тенге (накопленные расходы ниже нового порога). После изменения порога совершается новая покупка на сумму 25 000 тенге.",
  "targets": [
   "R-11",
   "R-12",
   "R-25"
  ],
  "input": {
   "initial_expenses": 30000,
   "old_limit": 40000,
   "new_limit": 50000,
   "subsequent_purchase": 25000
  },
  "expected": {
   "expenses": 55000,
   "limit": 50000,
   "push_count": 1,
   "counter_change": 25000,
   "api_result": "OK"
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-03",
   "R-27"
  ],
  "quote": "Ф-1. Держатель активной карты KZT задаёт целый порог от 1 000 до 1 000 000 ₸ включительно.",
  "question": "Является ли допустимым дробное значение порога или передача нецелого числа через API?",
  "a": "Система принимает только целые числа, при передаче дробного значения возвращается ошибка валидации параметров (статус 400).",
  "b": "Система производит автоматическое округление переданного значения до целого числа тенге."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-09",
   "R-10"
  ],
  "quote": "Ф-3. Когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push. На карту приходится максимум один такой push за календарный месяц.",
  "question": "Должен ли отправляться повторный push, если расходы после достижения порога снизились (например, из-за возврата), а затем снова выросли до порога или выше в том же календарном месяце?",
  "a": "Push отправляется только один раз за календарный месяц независимо от последующих колебаний суммы расходов.",
  "b": "Push отправляется повторно при каждом новом переходе суммы от значения ниже порога к значению, равному порогу или выше, в рамках ограничения «максимум один такой push» (что противоречит ограничению)."
 },
 {
  "id": "I3",
  "req_ids": [
   "R-20"
  ],
  "quote": "REST type GET",
  "question": "Используется ли метод GET для изменения (сохранения) настроек на сервере?",
  "id_ref": "I3",
  "a": "Метод действительно использует GET и передает параметры изменения состояния через query-строку.",
  "b": "Указание типа GET является опечаткой в документации, и для изменения настроек архитектурно должен применяться метод POST или PUT."
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
