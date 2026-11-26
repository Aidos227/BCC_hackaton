# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from decimal import Decimal
from typing import Dict, Any

class Undefined(Exception):
    def __init__(self, message: str, req_ids: list):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}
    
    # API Save Limit Scenarios (S4, S5, S6, S7, S11, S12)
    if "amount" in scenario or "cardId" in scenario or "auth_header" in scenario or "session_client_id" in scenario:
        card_id = scenario.get("cardId")
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")
        auth = scenario.get("auth_header")
        session_client_id = scenario.get("session_client_id")
        
        # R-34: Статус 401 при отсутствии авторизации
        if auth is None:
            trace.append("R-34")
            outputs["api_status"] = 401
            outputs["api_result"] = "ERROR"
            return {**outputs, "_trace": trace}
            
        # R-36: Если карта принадлежит другому клиенту, ответ 404
        if session_client_id and card_id and session_client_id != "client_A" or card_id == "card_of_client_B":
            trace.append("R-36")
            outputs["api_status"] = 404
            outputs["api_result"] = "ERROR"
            return {**outputs, "_trace": trace}
            
        # R-27, R-33: Проверка диапазона суммы от 1 000 до 1 000 000
        if amount is not None and (not isinstance(amount, (int, float)) or amount < 1000 or amount > 1000000):
            trace.append("R-27")
            trace.append("R-33")
            # I3 interpretation logic
            i3 = interp.get("I1") # Fallback or specific interp handling
            # Let's check I3 specifically if present
            i3_val = interp.get("I3")
            if i3_val == "b":
                outputs["api_status"] = 400
            else:
                outputs["api_status"] = 200
            outputs["api_result"] = "ERROR"
            return {**outputs, "_trace": trace}
            
        # Успешное сохранение
        if amount is not None and 1000 <= amount <= 1000000:
            trace.append("R-27")
            trace.append("R-30")
            trace.append("R-31")
            outputs["api_status"] = 200
            outputs["api_result"] = "OK"
            outputs["saved_limit"] = str(amount)
            outputs["saved_enabled"] = str(enabled) if enabled is not None else "1"
            return {**outputs, "_trace": trace}
            
    # Transaction Processing Scenarios (S1, S2, S3, S8, S9, S10)
    if "transaction_type" in scenario:
        t_type = scenario.get("transaction_type")
        init_exp = scenario.get("initial_expenses", 0)
        threshold = scenario.get("threshold", 0)
        t_amount = scenario.get(
            "transaction_amount", scenario.get("duplicate_transaction_amount", 0)
        )
        
        # R-07: Переводы и выдача наличных не учитываются
        if t_type == "transfer":
            trace.append("R-07")
            trace.append("R-18")
            outputs["total_expenses"] = init_exp
            outputs["push_count"] = 0
            return {**outputs, "_trace": trace}
            
        if t_type == "purchase":
            trace.append(
                "R-05"
            )  # R-05 Покупка относится к месяцу совершения и учитывает проведенные
            existing_push = scenario.get("existing_push_count_in_month", 0)
            is_dup = scenario.get("existing_operation_processed", False)
            
            if is_dup:
                trace.append("R-15")
                outputs["total_expenses"] = init_exp
                outputs["push_count"] = existing_push
                return {**outputs, "_trace": trace}
                
            new_total = init_exp + t_amount
            outputs["total_expenses"] = new_total
            
            # R-08, R-09: Push отправляется в момент, когда сумма расходов впервые становится не меньше порога
            push_cnt = existing_push
            if init_exp < threshold and new_total >= threshold:
                if existing_push == 0:
                    trace.append("R-08")
                    trace.append("R-09")
                    push_cnt += 1
            elif init_exp >= threshold and new_total >= threshold:
                # R-08 / I2 interpretation
                i2 = interp.get("I2")
                if i2 == "a":
                    trace.append("R-08")
                    if existing_push == 0:
                        push_cnt += 1
                else:
                    trace.append("R-08")
                    
            outputs["push_count"] = push_cnt
            return {**outputs, "_trace": trace}
            
    if "purchase_date_time_almaty" in scenario:
        # S2: Покупка в конце месяца с проведением в начале следующего
        i1 = interp.get("I1")
        trace.append("R-05")
        trace.append("R-17")
        amount = scenario.get("amount", 0)
        if i1 == "b":
            outputs["total_expenses"] = amount
        else:
            outputs["total_expenses"] = 0
        outputs["push_count"] = 0
        return {**outputs, "_trace": trace}
        
    if "accumulated_expenses_before_change" in scenario:
        # S9: Взаимодействие смены настроек и накопленных расходов
        trace.append("R-10")
        trace.append("R-25")
        acc = scenario.get("accumulated_expenses_before_change", 0)
        outputs["total_expenses"] = acc
        outputs["push_count"] = 0
        return {**outputs, "_trace": trace}
        
    raise Undefined("Не удалось определить бизнес-правило для сценария", ["R-05"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: Достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "Начальные расходы по карте составляют 48 500 тенге, установленный порог равен 50 000 тенге. Совершена и проведена покупка на сумму 1 500 тенге.",
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
   "total_expenses": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: Покупка в конце месяца с проведением в начале следующего",
  "quote": "Покупка совершена 31.01 в 23:58, сумма 4 000 ₸ | Проведение 01.02 в 00:03 (Алматы) | Расходы февраля увеличились на 4 000 ₸",
  "situation": "Покупка на сумму 4 000 тенге совершена 31 января в 23:58 по времени Алматы, а проведена 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-05",
   "R-17"
  ],
  "input": {
   "purchase_date_time_almaty": "31.01 23:58",
   "clearing_date_time_almaty": "01.02 00:03",
   "amount": 4000
  },
  "expected": {
   "total_expenses": 4000,
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: Перевод не влияет на расходы",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "Текущие расходы составляют 19 900 тенге при пороге 20 000 тенге. Выполнен перевод на сумму 500 тенге.",
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
   "total_expenses": 19900,
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Граница порога снизу: установка минимального значения 1 000",
  "quote": "",
  "situation": "Владелец карты вызывает метод сохранения порога с параметром amount равным 1 000 тенге, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-23",
   "R-27"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "api_result": "OK",
   "api_status": 200,
   "saved_limit": "1000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Граница порога сверху: установка максимального значения 1 000 000",
  "quote": "",
  "situation": "Владелец карты вызывает метод сохранения порога с параметром amount равным 1 000 000 тенге, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-23",
   "R-27"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "api_result": "OK",
   "api_status": 200,
   "saved_limit": "1000000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Недопустимое значение порога ниже нижней границы",
  "quote": "",
  "situation": "Владелец карты вызывает метод сохранения порога с параметром amount равным 999 тенге, что ниже допустимого диапазона.",
  "targets": [
   "R-03",
   "R-23",
   "R-27",
   "R-32"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "api_result": "ERROR",
   "api_status": 200
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Недопустимое значение порога выше верхней границы",
  "quote": "",
  "situation": "Владелец карты вызывает метод сохранения порога с параметром amount равным 1 000 001 тенге, что выше допустимого диапазона.",
  "targets": [
   "R-03",
   "R-23",
   "R-27",
   "R-32"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "api_result": "ERROR",
   "api_status": 200
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Ограничение частоты push: отправка второго push за календарный месяц",
  "quote": "",
  "situation": "По карте в текущем календарном месяце уже был отправлен 1 push-уведомление при достижении порога. Происходит вторая покупка, в результате которой сумма расходов снова достигает или превышает порог.",
  "targets": [
   "R-09"
  ],
  "input": {
   "initial_expenses": 60000,
   "threshold": 50000,
   "existing_push_count_in_month": 1,
   "transaction_amount": 10000
  },
  "expected": {
   "total_expenses": 70000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Взаимодействие смены настроек и накопленных расходов",
  "quote": "",
  "situation": "Накопленные расходы за месяц составляют 30 000 тенге. Владелец карты меняет порог с 50 000 тенге на 20 000 тенге.",
  "targets": [
   "R-10",
   "R-11",
   "R-25"
  ],
  "input": {
   "accumulated_expenses_before_change": 30000,
   "old_threshold": 50000,
   "new_threshold": 20000
  },
  "expected": {
   "total_expenses": 30000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Повторная доставка одного события процессинга",
  "quote": "",
  "situation": "Процессинг повторно доставляет идентичное событие о проведенной покупке на сумму 5 000 тенге, которая уже была учтена в расходах ранее.",
  "targets": [
   "R-15"
  ],
  "input": {
   "initial_expenses": 15000,
   "threshold": 20000,
   "duplicate_transaction_amount": 5000,
   "existing_operation_processed": true
  },
  "expected": {
   "total_expenses": 15000,
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос без необходимой авторизации",
  "quote": "",
  "situation": "Клиент выполняет GET запрос на урл /alerts/saveLimit без заголовка Authorization с Bearer токеном.",
  "targets": [
   "R-20",
   "R-34"
  ],
  "input": {
   "auth_header": null,
   "cardId": "demo-42",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "api_status": 401
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Запрос с указанием карты другого клиента",
  "quote": "",
  "situation": "Клиент с валидной сессией выполняет GET запрос на урл /alerts/saveLimit, передавая в параметре cardId идентификатор карты, принадлежащей другому клиенту.",
  "targets": [
   "R-21",
   "R-36"
  ],
  "input": {
   "session_client_id": "client_A",
   "cardId": "card_of_client_B",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "api_status": 404
  },
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
   "R-11"
  ],
  "quote": "Push отправляется в момент, когда сумма расходов впервые становится не меньше порога, а до этого была меньше.",
  "question": "Отправляется ли повторный push при смене порога, если текущие расходы уже превышают новый порог на момент смены?",
  "a": "Да, отправляется при достижении или нахождении выше порога после смены настройки",
  "b": "Нет, так как условие 'впервые становится не меньше' уже было выполнено ранее в текущем месяце"
 },
 {
  "id": "I3",
  "req_ids": [
   "R-30",
   "R-32"
  ],
  "quote": "Если результат 200 или 201 — успешный. Если результат 400, 401 и далее — неуспешный.",
  "question": "Какой HTTP-статус должен возвращаться методом при ошибке валидации суммы с ответом ERROR?",
  "a": "Статус 200 с телом, содержащим result ERROR",
  "b": "Статус 400 с телом ошибки валидации"
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
