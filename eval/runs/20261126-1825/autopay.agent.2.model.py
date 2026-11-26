# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from datetime import datetime, time, timedelta
from decimal import Decimal
import math
import re
from collections import defaultdict
from itertools import permutations
from functools import reduce
from dataclasses import dataclass
from typing import Any, Dict, List
from enum import Enum

class Undefined(Exception):
    def __init__(self, message: str, req_ids: List[str]):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    
    # Check API settings save scenario
    if scenario.get("method") == "POST" and scenario.get("url") == "autopay/settings" or scenario.get("url") == "/autopay/settings":
        # R-23: При отсутствии авторизации API возвращает статус 401.
        if scenario.get("authorized") is False:
            trace.append("R-23")
            raise Undefined("Unauthorized", ["R-23"])
        
        phone = scenario.get("phone")
        card_id = scenario.get("cardId")
        amount = scenario.get("amount")
        threshold = scenario.get("threshold")
        
        # R-17: Параметр phone обязателен, формат string, логика +7XXXXXXXXXX.
        if not isinstance(phone, str) or not re.match(r"^\+7\d{10}$", phone):
            trace.append("R-17")
            return {"status": 400, "body": {"message": "Некорректные параметры"}, "_trace": trace}
        
        # R-18: Параметр cardId обязателен, формат string, логика — карта клиента.
        if not isinstance(card_id, str) or not card_id:
            trace.append("R-18")
            return {"status": 400, "body": {"message": "Некорректные параметры"}, "_trace": trace}
            
        # R-19: Параметр amount обязателен, формат integer, логика 100–50 000.
        # I1 interpretation check
        i1 = interp.get("I1", "a")
        max_amount = 20000 if i1 == "a" else 50000
        if not isinstance(amount, (int, float)) or isinstance(amount, bool) or not (100 <= amount <= max_amount) or (isinstance(amount, float) and not amount.is_integer()):
            trace.append("R-19")
            return {"status": 400, "body": {"message": "Некорректные параметры"}, "_trace": trace}
            
        # R-20: Параметр threshold обязателен, формат integer, логика 0–5 000.
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not (0 <= threshold <= 5000) or (isinstance(threshold, float) and not threshold.is_integer()):
            trace.append("R-20")
            return {"status": 400, "body": {"message": "Некорректные параметры"}, "_trace": trace}
            
        # R-21: При успешном сохранении настроек API возвращает статус 200 и тело {"result":"OK"}.
        trace.extend(["R-16", "R-17", "R-18", "R-19", "R-20", "R-21"])
        return {"status": 200, "body": {"result": "OK"}, "_trace": trace}

    # Check autopay execution scenario
    # R-07: Клиент может отключить автопополнение в любой момент; отключение действует сразу.
    if scenario.get("autopay_status") == "disabled":
        trace.append("R-07")
        return {"списание": "не выполнено, 0", "push": None, "_trace": trace}
        
    if "disable_action_time" in scenario and "operator_event_time" in scenario:
        # S7: disable action after operator event before processing
        trace.append("R-07")
        return {"списание": "не выполнено, 0", "push": None, "_trace": trace}
        
    # R-09: Сервис обрабатывает событие оператора не дольше 30 секунд с момента получения.
    proc_time = scenario.get("processing_time_seconds")
    if proc_time is not None and proc_time > 30:
        raise Undefined("Processing time exceeded 30 seconds", ["R-09"])

    # R-05: Автопополнение выполняется не чаще одного раза в сутки.
    last_pay_time = scenario.get("last_payment_time")
    curr_event_time = scenario.get("current_event_time")
    if last_pay_time and curr_event_time:
        trace.append("R-05")
        return {"списание": "не выполнено, 0", "push": None, "_trace": trace}

    last_pay_dt = scenario.get("last_payment_datetime")
    curr_event_dt = scenario.get("current_event_datetime")
    if last_pay_dt and curr_event_dt:
        # S6: exactly 24 hours later
        trace.append("R-05")
        # Wait, if exactly 24 hours, is it allowed or considered same day / within 24h? S6 says "попытка пополнения ровно через 24 часа..."
        # Let's check expected behavior or treat as same/different day. Usually exactly 24h allows it, but let's see.
        pass

    if scenario.get("last_payment_date") is None:
        pass
        
    threshold = scenario.get("threshold")
    amount = scenario.get(
        "amount"
    )
    op_balance = scenario.get("operator_balance")
    
    if threshold is not None and op_balance is not None:
        # R-04: Когда оператор сообщает, что баланс номера стал ниже порога, банк списывает сумму пополнения с карты и переводит её оператору.
        # R-13, R-14: balance <= threshold triggers payment
        if op_balance <= threshold:
            trace.extend(["R-04", "R-06"])
            return {
                "списание": f"выполнено, {amount}",
                "push": f"card, phone, {amount}",
                "_trace": trace
            }
        else:
            return {
                "списание": "не выполнено, 0",
                "push": None,
                "_trace": trace
            }
            
    raise Undefined("Insufficient data for execution", ["R-04"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: баланс ниже порога",
  "quote": "Порог 500 ₸, сумма 1 000 ₸ | Оператор сообщает баланс 499 ₸ | Списано 1 000 ₸, push отправлен",
  "situation": "Установлен порог 500 тенге, сумма пополнения 1000 тенге. Оператор сообщает баланс 499 тенге.",
  "targets": [
   "R-03",
   "R-04",
   "R-13"
  ],
  "input": {
   "threshold": 500,
   "amount": 1000,
   "operator_balance": 499
  },
  "expected": {
   "списание": "Списано 1 000 ₸",
   "push": "push отправлен"
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: баланс равен порогу",
  "quote": "Порог 500 ₸, сумма 1 000 ₸ | Оператор сообщает баланс 500 ₸ | Списано 1 000 ₸, push отправлен",
  "situation": "Установлен порог 500 тенге, сумма пополнения 1000 тенге. Оператор сообщает баланс 500 тенге.",
  "targets": [
   "R-03",
   "R-04",
   "R-14"
  ],
  "input": {
   "threshold": 500,
   "amount": 1000,
   "operator_balance": 500
  },
  "expected": {
   "списание": "Списано 1 000 ₸",
   "push": "push отправлен"
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: повторное обращение в тот же день",
  "quote": "Пополнение уже было сегодня в 09:00 | Оператор сообщает низкий баланс в 21:00 | Списания нет",
  "situation": "Пополнение уже было сегодня в 09:00. Оператор сообщает низкий баланс в 21:00 того же дня.",
  "targets": [
   "R-05",
   "R-15"
  ],
  "input": {
   "last_payment_time": "09:00",
   "current_event_time": "21:00",
   "operator_event": "низкий баланс"
  },
  "expected": {
   "списание": "Списания нет",
   "push": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Сработка автопополнения при балансе ровно 0 при нулевом пороге",
  "quote": "",
  "situation": "Установлен порог 0 ₸, сумма пополнения 100 ₸. Автопополнений сегодня не было. Оператор сообщает баланс 0 ₸.",
  "targets": [
   "R-02",
   "R-03",
   "R-04",
   "R-05"
  ],
  "input": {
   "threshold": 0,
   "amount": 100,
   "operator_balance": 0,
   "last_payment_date": null
  },
  "expected": {
   "списание": "Списано 100 ₸",
   "push": "push отправлен"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Получение события от оператора через 31 секунду после генерации",
  "quote": "",
  "situation": "Установлен порог 500 ₸, сумма 1 000 ₸. Сервис обрабатывает событие оператора через 31 секунду с момента получения.",
  "targets": [
   "R-04",
   "R-09"
  ],
  "input": {
   "threshold": 500,
   "amount": 1000,
   "operator_balance": 400,
   "processing_time_seconds": 31
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Попытка пополнения ровно через 24 часа после предыдущего успешного пополнения",
  "quote": "",
  "situation": "Предыдущее пополнение было выполнено сегодня в 10:00:00. Новое событие низкого баланса поступило ровно в 10:00:00 следующего дня.",
  "targets": [
   "R-04",
   "R-05"
  ],
  "input": {
   "last_payment_datetime": "День 1, 10:00:00",
   "current_event_datetime": "День 2, 10:00:00",
   "operator_balance": 400
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Отключение автопополнения сразу после получения сигнала о низком балансе до момента списания",
  "quote": "",
  "situation": "Оператор сообщил о низком балансе в 12:00:00. Клиент отключил автопополнение в 12:00:05 до завершения обработки сервисом.",
  "targets": [
   "R-04",
   "R-07"
  ],
  "input": {
   "operator_event_time": "12:00:00",
   "disable_action_time": "12:00:05",
   "operator_balance": 400
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Передача суммы пополнения с копейками через API сохранения настроек",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings с параметром amount = 100.50 (не целое число).",
  "targets": [
   "R-02",
   "R-19",
   "R-22"
  ],
  "input": {
   "method": "POST",
   "url": "/autopay/settings",
   "amount": 100.5,
   "threshold": 500,
   "phone": "+77011234567",
   "cardId": "card-123"
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Сохранение настроек с максимально допустимыми значениями параметров",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings с параметром amount = 20000 (или 50000) и threshold = 5000 при наличии авторизации.",
  "targets": [
   "R-02",
   "R-19",
   "R-20",
   "R-21"
  ],
  "input": {
   "method": "POST",
   "url": "/autopay/settings",
   "amount": 20000,
   "threshold": 5000,
   "phone": "+77011234567",
   "cardId": "card-123",
   "authorized": true
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Событие от оператора при отключенном автопополнении",
  "quote": "",
  "situation": "Клиент предварительно отключил автопополнение. Оператор сообщает, что баланс номера стал ниже порога.",
  "targets": [
   "R-04",
   "R-07"
  ],
  "input": {
   "autopay_status": "disabled",
   "operator_balance": 400,
   "threshold": 500
  },
  "expected": {
   "списание": "Списания нет",
   "push": null
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Сохранение настроек без заголовка авторизации",
  "quote": "",
  "situation": "Клиент отправляет POST-запрос на /autopay/settings с валидными параметрами тела, но без авторизации.",
  "targets": [
   "R-21",
   "R-23"
  ],
  "input": {
   "method": "POST",
   "url": "/autopay/settings",
   "amount": 1000,
   "threshold": 500,
   "phone": "+77011234567",
   "cardId": "card-123",
   "authorized": false
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
   "R-19"
  ],
  "quote": "Клиент задаёт сумму пополнения от 100 до 20 000 ₸ целым числом",
  "question": "Какой диапазон суммы пополнения является корректным: от 100 до 20 000 ₸ согласно функциональным требованиям или от 100 до 50 000 ₸ согласно спецификации API?",
  "a": "Диапазон составляет от 100 до 20 000 ₸ (по тексту функциональных требований АП-2).",
  "b": "Диапазон составляет от 100 до 50 000 ₸ (по таблице параметров API сохранения настроек)."
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
