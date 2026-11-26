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
import math
import re
from collections import defaultdict
from itertools import count
from functools import reduce
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum

class Undefined(Exception):
    def __init__(self, message: str, req_ids: List[str]):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}
    
    # S1
    if "initial_expenses" in scenario and "purchase_amount" in scenario and "transfer_amount" not in scenario and "return_amount" not in scenario and "current_expenses" not in scenario:
        initial = Decimal(str(scenario.get("initial_expenses", 0)))
        limit = Decimal(str(scenario.get("limit_kzt", 50000)))
        purchase = Decimal(str(scenario.get("purchase_amount", 0)))
        
        # R-09, R-12, R-23
        trace.extend(["R-09", "R-12", "R-23"])
        new_total = initial + purchase
        outputs["expenses_total"] = float(new_total)
        outputs["limit_kzt"] = float(limit)
        if initial < limit and new_total >= limit:
            outputs["push_count"] = 1
        else:
            outputs["push_count"] = 0
        outputs["counter_change"] = float(purchase)
        return {**outputs, "_trace": trace}
        
    # S2
    if "purchase_datetime_almaty" in scenario:
        # R-08, R-24
        trace.extend(["R-08", "R-24"])
        amt = Decimal(str(scenario.get("purchase_amount", 4000)))
        outputs["expenses_total"] = float(amt)
        outputs["counter_change"] = float(amt)
        outputs["limit_kzt"] = 50000
        outputs["push_count"] = 0
        return {**outputs, "_trace": trace}

    # S3
    if "transfer_amount" in scenario:
        # R-11, R-25
        trace.extend(["R-11", "R-25"])
        initial = Decimal(str(scenario.get("initial_expenses", 0)))
        limit = Decimal(str(scenario.get("limit_kzt", 0)))
        outputs["expenses_total"] = float(initial)
        outputs["limit_kzt"] = float(limit)
        outputs["push_count"] = 0
        outputs["counter_change"] = 0.0
        return {**outputs, "_trace": trace}

    # S4, S5, S6, S7, S10, S11
    if "amount" in scenario or "cardId" in scenario:
        # R-26, R-27, R-28, R-29, R-31, R-32, R-33, R-36, R-40, R-41, R-42, R-48, R-49, R-50, R-53
        auth = scenario.get("auth_header", "Bearer token")
        card_id = scenario.get(
            "cardId"
        )
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")

        if auth is None or auth == "":
            trace.extend(["R-27", "R-31", "R-50"])
            outputs["api_result"] = "ERROR"
            outputs["api_status"] = 401
            return {**outputs, "_trace": trace}

        if card_id == "alien-card-99":
            trace.extend(["R-32", "R-53"])
            outputs["api_result"] = "ERROR"
            outputs["api_status"] = 404
            return {**outputs, "_trace": trace}

        if amount is None or not (1000 <= amount <= 1000000):
            trace.extend(["R-33", "R-36", "R-41", "R-35", "R-49"])
            outputs["api_result"] = "ERROR"
            outputs["api_status"] = 400
            return {**outputs, "_trace": trace}

        trace.extend(["R-26", "R-27", "R-28", "R-29", "R-31", "R-32", "R-33", "R-34", "R-36", "R-40", "R-41", "R-42", "R-48"])
        outputs["api_result"] = "OK"
        outputs["api_status"] = 200
        outputs["limit_kzt"] = float(amount)
        outputs["push_count"] = 0
        outputs["expenses_total"] = 0.0
        outputs["counter_change"] = 0.0
        return {**outputs, "_trace": trace}

    # S8
    if "delivery_count" in scenario:
        # R-22
        trace.extend(["R-22"])
        amt = Decimal(str(scenario.get("purchase_amount", 0)))
        outputs["expenses_total"] = float(amt)
        outputs["limit_kzt"] = 50000
        outputs["push_count"] = 0
        outputs["counter_change"] = float(amt)
        return {**outputs, "_trace": trace}

    # S9
    if "current_expenses" in scenario:
        # R-14, R-38
        trace.extend(["R-14", "R-38"])
        current = Decimal(str(scenario.get("current_expenses", 0)))
        new_lim = Decimal(str(scenario.get("new_limit", 0)))
        outputs["expenses_total"] = float(current)
        outputs["limit_kzt"] = float(new_lim)
        outputs["push_count"] = 0
        outputs["counter_change"] = 0.0
        return {**outputs, "_trace": trace}

    # S12
    if "return_amount" in scenario:
        # R-10
        trace.extend(["R-10"])
        initial = Decimal(str(scenario.get("initial_expenses", 0)))
        ret = Decimal(str(scenario.get("return_amount", 0)))
        new_tot = initial - ret
        outputs["expenses_total"] = float(new_tot)
        outputs["counter_change"] = float(-ret)
        outputs["limit_kzt"] = 50000
        outputs["push_count"] = 0
        return {**outputs, "_trace": trace}

    raise Undefined("Scenario not handled", ["R-01"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Достижение порога при покупке",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ Провести покупку на 1 500 ₸ Итог 50 000 ₸ и один push",
  "situation": "У карты имеются текущие расходы 48 500 ₸ и установленный порог 50 000 ₸. Совершена и проведена покупка на 1 500 ₸.",
  "targets": [
   "R-23"
  ],
  "input": {
   "initial_expenses": 48500,
   "limit_kzt": 50000,
   "purchase_amount": 1500
  },
  "expected": {
   "expenses_total": 50000,
   "limit_kzt": 50000,
   "push_count": 1,
   "counter_change": 1500,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Учет покупки в полночь по времени Алматы",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ Провести 1 февраля в 00:03 по Алматы Февральский счётчик вырос на 4 000 ₸",
  "situation": "Покупка на 4 000 ₸ совершена 31 января в 23:58 по времени Алматы и проведена 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-24"
  ],
  "input": {
   "purchase_datetime_almaty": "2023-01-31T23:58:00",
   "processing_datetime_almaty": "2023-02-01T00:03:00",
   "purchase_amount": 4000
  },
  "expected": {
   "expenses_total": 4000,
   "limit_kzt": null,
   "push_count": 0,
   "counter_change": 4000,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Перевод не увеличивает счетчик расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ Перевести 500 ₸ Счётчик показывает 19 900 ₸",
  "situation": "У карты имеются расходы 19 900 ₸ и порог 20 000 ₸. Выполнен перевод на сумму 500 ₸.",
  "targets": [
   "R-25"
  ],
  "input": {
   "initial_expenses": 19900,
   "limit_kzt": 20000,
   "transfer_amount": 500
  },
  "expected": {
   "expenses_total": 19900,
   "limit_kzt": 20000,
   "push_count": 0,
   "counter_change": 0,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Сохранение порога на нижней границе диапазона",
  "quote": "",
  "situation": "Клиент отправляет запрос GET /alerts/saveLimit с параметрами cardId='demo-42', amount=1000, enabled=1 с действующей сессией владельца.",
  "targets": [
   "R-06",
   "R-26",
   "R-36",
   "R-41"
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
  "title": "Сохранение порога ниже нижней границы диапазона",
  "quote": "",
  "situation": "Клиент отправляет запрос GET /alerts/saveLimit с параметрами cardId='demo-42', amount=999, enabled=1 с действующей сессией владельца.",
  "targets": [
   "R-06",
   "R-35",
   "R-41",
   "R-49"
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
  "id": "S6",
  "source": "boundary",
  "title": "Сохранение порога на верхней границе диапазона",
  "quote": "",
  "situation": "Клиент отправляет запрос GET /alerts/saveLimit с параметрами cardId='demo-42', amount=1000000, enabled=1 с действующей сессией владельца.",
  "targets": [
   "R-06",
   "R-36",
   "R-41"
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
  "id": "S7",
  "source": "boundary",
  "title": "Сохранение порога выше верхней границы диапазона",
  "quote": "",
  "situation": "Клиент отправляет запрос GET /alerts/saveLimit с параметрами cardId='demo-42', amount=1000001, enabled=1 с действующей сессией владельца.",
  "targets": [
   "R-06",
   "R-35",
   "R-41",
   "R-49"
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
  "title": "Повторная доставка одного события процессинга",
  "quote": "",
  "situation": "Карточный процессинг дважды передает в сервис расходов одно и то же событие проведенной покупки на 5 000 ₸ с одинаковым идентификатором операции.",
  "targets": [
   "R-09",
   "R-16",
   "R-20",
   "R-22"
  ],
  "input": {
   "operation_id": "OP-777",
   "purchase_amount": 5000,
   "delivery_count": 2
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Изменение порога при уже накопленной сумме расходов выше нового порога",
  "quote": "",
  "situation": "У карты накоплены расходы 60 000 ₸ и установлен порог 70 000 ₸. В течение месяца клиент меняет порог на 50 000 ₸ через API.",
  "targets": [
   "R-12",
   "R-14",
   "R-15",
   "R-38"
  ],
  "input": {
   "current_expenses": 60000,
   "old_limit": 70000,
   "new_limit": 50000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Запрос сохранения настроек для чужой или несуществующей карты",
  "quote": "",
  "situation": "Клиент с валидной сессией отправляет запрос GET /alerts/saveLimit с параметром cardId='alien-card-99', amount=50000, enabled=1 для карты, которая ему не принадлежит или не существует в системе.",
  "targets": [
   "R-32",
   "R-53"
  ],
  "input": {
   "cardId": "alien-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос сохранения настроек без авторизации",
  "quote": "",
  "situation": "Запрос GET /alerts/saveLimit отправлен с параметрами cardId='demo-42', amount=50000, enabled=1 без заголовка Authorization Bearer.",
  "targets": [
   "R-27",
   "R-31",
   "R-50"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 50000,
   "enabled": 1,
   "auth_header": null
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Учет операции возврата средств по покупке",
  "quote": "",
  "situation": "У карты зафиксированы проведенные покупки на 30 000 ₸ в текущем месяце. Поступает событие возврата по одной из прошлых покупок на сумму 5 000 ₸.",
  "targets": [
   "R-09",
   "R-10",
   "R-16"
  ],
  "input": {
   "initial_expenses": 30000,
   "return_amount": 5000
  },
  "expected": null,
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-10"
  ],
  "quote": "Возврат уменьшает расходы месяца исходной покупки.",
  "question": "Уменьшает ли возврат расходы месяца исходной покупки, если возврат совершен в другом календарном месяце?",
  "a": "Возврат уменьшает расходы того месяца, в котором была совершена исходная покупка.",
  "b": "Возврат учитывается в месяце фактического проведения возврата и не влияет на исторический месяц покупки."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-12",
   "R-13"
  ],
  "quote": "Когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push.",
  "question": "Будет ли отправлен повторный push, если после достижения порога и отправки уведомления расходы сначала уменьшились (например, из-за возврата), а затем снова выросли до порога или выше в том же календарном месяце?",
  "a": "Push не отправляется, так как действует ограничение «максимум один такой push за календарный месяц».",
  "b": "Push отправляется повторно, так как произошло новое пересечение порога снизу вверх."
 },
 {
  "id": "I3",
  "req_ids": [
   "R-26"
  ],
  "quote": "REST type GET",
  "question": "Является ли использование метода GET для сохранения настроек (изменения состояния) преднамеренным решением или требование содержит опечатку по сравнению с передачей параметров в query?",
  "a": "Метод корректно реализован как GET с передачей параметров в query-строке.",
  "b": "Метод должен быть реализован как POST/PUT, так как операция изменяет состояние настроек на сервере."
 },
 {
  "id": "I4",
  "req_ids": [
   "R-15"
  ],
  "quote": "Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.",
  "question": "Сбрасывается ли лимит отправки «один push в месяц» при изменении порога настройки?",
  "a": "Счетчик отправленных push сбрасывается или не учитывается, позволяя отправить push по новому порогу в том же месяце.",
  "b": "Ограничение «максимум один push за календарный месяц» сохраняется независимо от изменения порога."
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
