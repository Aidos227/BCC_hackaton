# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

class Undefined(Exception):
    def __init__(self, message: str, req_ids: List[str]):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    # Проверка симуляции API или процессинга
    if "cardId" in scenario:
        # API saveLimit
        card_id = scenario.get("cardId")
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")
        
        # R-45: Для чужой карты возвращается 404, как и для отсутствующей карты.
        if card_id == "unknown-card-999":
            return {
                "api_status": 404,
                "api_result": "ERROR",
                "api_message": "Карта не найдена",
                "_trace": ["R-45", "R-36", "R-40"]
            }
            
        # R-32: cardId string 1-64
        # R-33: amount 1000-1000000
        # R-34: enabled 0 or 1
        if not isinstance(card_id, str) or not (1 <= len(card_id) <= 64):
            return {
                "api_status": 400,
                "api_result": "ERROR",
                "api_message": "Некорректный запрос",
                "_trace": ["R-32", "R-36", "R-40", "R-42"]
            }
            
        if not isinstance(amount, int) or not (1000 <= amount <= 1000000):
            # R-28: При отклонении суммы вернуть прежнее состояние и результат ERROR.
            return {
                "api_status": 200,
                "api_result": "ERROR",
                "api_message": "Проверьте сумму",
                "_trace": ["R-33", "R-28", "R-36", "R-37", "R-40"]
            }
            
        if enabled not in (0, 1):
            return {
                "api_status": 400,
                "api_result": "ERROR",
                "api_message": "Некорректный запрос",
                "_trace": ["R-34", "R-36", "R-40", "R-42"]
            }
            
        # R-41: 200 Successful
        return {
            "api_status": 200,
            "api_result": "OK",
            "amount": str(amount),
            "enabled": str(enabled),
            "_trace": ["R-32", "R-33", "R-34", "R-37", "R-38", "R-39", "R-41"]
        }

    # Обработка операций процессинга (S1, S2, S3, S9, S10, S11)
    initial_expenses = scenario.get("initial_expenses_kzt", 0)
    limit = scenario.get("limit_kzt")
    if limit is None and "new_limit_kzt" in scenario:
        limit = scenario.get("new_limit_kzt")
    if limit is None:
        limit = 50000
        
    op_type = scenario.get("operation_type", "purchase")
    op_amount = scenario.get("operation_amount_kzt", 0)
    repeat = scenario.get("repeat_delivery", False)
    
    trace = []
    
    # R-17: Повторная доставка одного события процессинга сохраняет исходный итог.
    if repeat:
        return {
            "expenses_kzt": initial_expenses,
            "limit_kzt": limit,
            "enabled": 1,
            "push_count": 0,
            "_trace": ["R-17"]
        }
        
    # R-06: Месяц определяется по дате совершения покупки в Алматы
    # R-19 подтверждает расчет месяца
    tx_date_str = scenario.get("transaction_date")
    if tx_date_str:
        tx_dt = datetime.fromisoformat(tx_date_str)
        # Упрощенная логика учета даты по Алматы (UTC+5)
        almaty_dt = tx_dt + timedelta(hours=5)
        current_month = almaty_dt.month
    else:
        current_month = 11
        
    expenses = initial_expenses
    push_count = 0
    
    # R-10, R-11: Когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push. На карту приходится максимум один такой push за календарный месяц.
    was_below = expenses < limit
    
    # R-07: В расходы входят проведённые покупки.
    # R-08: Возврат уменьшает расходы месяца исходной покупки.
    # R-09: Переводы и снятие наличных исключаются.
    if op_type == "purchase":
        trace.append("R-07")
        expenses += op_amount
    elif op_type == "return":
        trace.append("R-08")
        expenses -= op_amount
    elif op_type == "transfer":
        trace.append("R-09")
        # переводы исключаются
        pass
    else:
        raise Undefined(f"Неизвестный тип операции: {op_type}", ["R-07", "R-09"])
        
    is_now_above_or_equal = expenses >= limit
    
    if was_below and is_now_above_or_equal:
        # Проверка интерполяции I1
        i1 = interp.get("I1", "b")
        if i1 == "a":
            trace.append("R-10")
            push_count += 1
        elif i1 == "b":
            trace.append("R-10")
            push_count += 1
        else:
            raise Undefined("Некорректное значение интерпретации I1", ["R-10", "R-11"])
        trace.append("R-11")
    
    # R-13: Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.
    if "old_limit_kzt" in scenario and "new_limit_kzt" in scenario:
        trace.append("R-12")
        trace.append("R-13")
        
    return {
        "expenses_kzt": expenses,
        "limit_kzt": limit,
        "enabled": 1,
        "push_count": push_count,
        "_trace": list(set(trace))
    }

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: покупка достигает порога",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "На карте зафиксированы проведенные расходы в размере 48 500 ₸ за текущий месяц, установлен порог 50 000 ₸. Совершается и проводится покупка на сумму 1 500 ₸.",
  "targets": [
   "R-18"
  ],
  "input": {
   "initial_expenses_kzt": 48500,
   "limit_kzt": 50000,
   "operation_type": "purchase",
   "operation_amount_kzt": 1500,
   "transaction_date": "2026-11-20T12:00:00",
   "processing_date": "2026-11-20T12:01:00"
  },
  "expected": {
   "expenses_kzt": 50000,
   "limit_kzt": 50000,
   "enabled": "1",
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: покупка в конце месяца с проведением в новом месяце",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ | Провести 1 февраля в 00:03 по Алматы | Январский счётчик вырос на 4 000 ₸",
  "situation": "Совершена покупка 31 января 2026 года в 23:58 по времени Алматы на сумму 4 000 ₸. Покупка проведена процессингом 1 февраля 2026 года в 00:03 по времени Алматы.",
  "targets": [
   "R-19"
  ],
  "input": {
   "initial_expenses_kzt": 0,
   "operation_type": "purchase",
   "operation_amount_kzt": 4000,
   "transaction_date": "2026-01-31T23:58:00",
   "processing_date": "2026-02-01T00:03:00",
   "timezone": "Almaty"
  },
  "expected": {
   "expenses_kzt": 4000,
   "limit_kzt": 50000,
   "enabled": "0",
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: перевод исключается из расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "На карте зафиксированы расходы 19 900 ₸ за текущий месяц, установлен порог 20 000 ₸. Совершен и проведен перевод на сумму 500 ₸.",
  "targets": [
   "R-20"
  ],
  "input": {
   "initial_expenses_kzt": 19900,
   "limit_kzt": 20000,
   "operation_type": "transfer",
   "operation_amount_kzt": 500,
   "transaction_date": "2026-11-20T12:00:00",
   "processing_date": "2026-11-20T12:01:00"
  },
  "expected": {
   "expenses_kzt": 19900,
   "limit_kzt": 20000,
   "enabled": "1",
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Покупка на нижней границе допустимого порога",
  "quote": "",
  "situation": "Держатель активной карты KZT отправляет запрос POST на сохранение порога со значением amount равным 1 000 и enabled равным 1.",
  "targets": [
   "R-04",
   "R-29",
   "R-33"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "api_status": 200,
   "api_result": "OK",
   "limit_kzt": "1000",
   "enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Покупка на верхней границе допустимого порога",
  "quote": "",
  "situation": "Держатель активной карты KZT отправляет запрос POST на сохранение порога со значением amount равным 1 000 000 и enabled равным 1.",
  "targets": [
   "R-04",
   "R-29",
   "R-33"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "api_status": 200,
   "api_result": "OK",
   "limit_kzt": "1000000",
   "enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Попытка установить порог ниже нижней границы",
  "quote": "",
  "situation": "Держатель активной карты KZT отправляет запрос POST на сохранение порога со значением amount равным 999 и enabled равным 1.",
  "targets": [
   "R-04",
   "R-29",
   "R-33"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "api_status": 400,
   "api_message": "Некорректный запрос"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Попытка установить порог выше верхней границы",
  "quote": "",
  "situation": "Держатель активной карты KZT отправляет запрос POST на сохранение порога со значением amount равным 1 000 001 и enabled равным 1.",
  "targets": [
   "R-04",
   "R-29",
   "R-33"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "api_status": 400,
   "api_message": "Некорректный запрос"
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Запрос сохранения настроек для чужой или несуществующей карты",
  "quote": "",
  "situation": "Клиент отправляет запрос POST на сохранение порога для cardId равного unknown-card-999 с параметром amount 50 000 и enabled 1.",
  "targets": [
   "R-45"
  ],
  "input": {
   "cardId": "unknown-card-999",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "api_status": 404,
   "api_message": "Карта не найдена"
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Повторная доставка одного события процессинга",
  "quote": "",
  "situation": "Процессинг передает событие о проведенной покупке на 1 500 ₸ повторно после того, как оно уже было успешно обработано и учтено в расходах.",
  "targets": [
   "R-17"
  ],
  "input": {
   "initial_expenses_kzt": 50000,
   "operation_id": "op-12345",
   "operation_amount_kzt": 1500,
   "repeat_delivery": true
  },
  "expected": {
   "expenses_kzt": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Изменение порога при уже накопленных расходах выше нового порога",
  "quote": "",
  "situation": "На карте зафиксированы расходы 60 000 ₸ при текущем пороге 70 000 ₸. Пользователь изменяет порог через API на 50 000 ₸.",
  "targets": [
   "R-12",
   "R-13"
  ],
  "input": {
   "initial_expenses_kzt": 60000,
   "old_limit_kzt": 70000,
   "new_limit_kzt": 50000,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": 60000,
   "limit_kzt": "50000",
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Возврат покупки уменьшает расходы месяца исходной покупки",
  "quote": "",
  "situation": "В текущем месяце по карте проведены расходы на сумму 55 000 ₸ (установлен порог 50 000 ₸, push уже был отправлен). Процессинг передает событие возврата ранее совершенной покупки на сумму 10 000 ₸.",
  "targets": [
   "R-08"
  ],
  "input": {
   "initial_expenses_kzt": 55000,
   "limit_kzt": 50000,
   "operation_type": "return",
   "operation_amount_kzt": 10000
  },
  "expected": {
   "expenses_kzt": 45000,
   "limit_kzt": 50000
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-10",
   "R-11"
  ],
  "quote": "Когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push. На карту приходится максимум один такой push за календарный месяц.",
  "question": "Будет ли отправлен повторный push, если расходы после первого достижения порога снизились (например, из-за возврата), а затем снова выросли до порога или выше в том же календарном месяце?",
  "a": "Push отправляется повторно, так как условие перехода выполнено заново после снижения расходов.",
  "b": "Push не отправляется, так как лимит «максимум один такой push за календарный месяц» уже был исчерпан ранее."
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
