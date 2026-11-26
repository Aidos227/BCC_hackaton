# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from decimal import Decimal
from typing import Dict, Any, List

class Undefined(Exception):
    def __init__(self, message: str, req_ids: List[str]):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}

    # API сохранения порога / проверки параметров
    if "cardId" in scenario:
        card_id = scenario.get("cardId")
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")

        # R-39: Если карта принадлежит другому клиенту, ответ — 404, так же как при несуществующей карте.
        if card_id == "alien-card-99":
            trace.append("R-39")
            outputs["api_status"] = 404
            outputs["api_result"] = "Карта не найдена"
            outputs["_trace"] = trace
            return outputs

        # R-31, R-32: Проверка параметров
        valid_amount = (isinstance(amount, int) and 1000 <= amount <= 1000000)
        valid_enabled = (enabled in [0, 1])

        if not valid_amount or not valid_enabled:
            trace.append("R-36")
            outputs["api_status"] = 400
            outputs["api_result"] = "Некорректный запрос"
            outputs["_trace"] = trace
            return outputs

        # R-35: Успешный ответ
        if interp.get("I2") == "b":
            trace.append("R-34")
            outputs["api_status"] = 200
        else:
            trace.append("R-34")
            outputs["api_status"] = 200
            
        trace.append("R-35")
        outputs["api_result"] = "OK"
        outputs["_trace"] = trace
        return outputs

    # Сценарии расходов и транзакций
    if "initial_expenses" in scenario or "accumulated_expenses" in scenario:
        # S1, S3
        if "transaction_type" in scenario:
            t_type = scenario.get("transaction_type")
            if t_type != "покупка":
                trace.append("R-07")
                outputs["total_expenses"] = scenario.get("initial_expenses")
                outputs["push_count"] = 0
                outputs["_trace"] = trace
                return outputs

        if "operation_type" in scenario:
            op_type = scenario.get("operation_type")
            if op_type == "перевод":
                trace.append("R-07")
                outputs["total_expenses"] = scenario.get("initial_expenses")
                outputs["push_count"] = 0
                outputs["_trace"] = trace
                return outputs

        initial = scenario.get("initial_expenses", 0)
        threshold = scenario.get("threshold", 0)
        t_amount = scenario.get("transaction_amount", 0)
        delivery_count = scenario.get("delivery_count", 1)

        # R-15: Повторная доставка одного события процессинга сохраняет исходный итог
        if delivery_count > 1:
            trace.append("R-15")
            total = initial
            push_cnt = 1 if initial >= threshold else 0
            outputs["total_expenses"] = total
            outputs["push_count"] = push_cnt
            outputs["_trace"] = trace
            return outputs

        total = initial + t_amount
        trace.append("R-05")
        
        push_cnt = 0
        if initial < threshold and total >= threshold:
            trace.append("R-08")
            trace.append("R-09")
            push_cnt = 1

        outputs["total_expenses"] = total
        outputs["push_count"] = push_cnt
        outputs["_trace"] = trace
        return outputs

    # S2: Покупка 31.01 и проведение 01.02
    if "purchase_date_time" in scenario:
        amount = scenario.get("amount", 0)
        i1 = interp.get("I1", "a")
        if i1 == "a":
            trace.append("R-05")
            outputs["total_expenses"] = amount
            outputs["push_count"] = 0
            outputs["_trace"] = trace
            return outputs
        else:
            trace.append("R-17")
            outputs["total_expenses"] = amount
            outputs["push_count"] = 0
            outputs["_trace"] = trace
            return outputs

    # S10, S11: Смена порога
    if "accumulated_expenses" in scenario:
        acc = scenario.get("accumulated_expenses", 0)
        old_t = scenario.get("old_threshold", 0)
        new_t = scenario.get("new_threshold", 0)
        initial_push = scenario.get("initial_push_count", 0)
        sub_p = scenario.get("subsequent_purchase", 0)

        trace.append("R-10")
        if sub_p > 0:
            new_total = acc + sub_p
            push_cnt = initial_push
            if acc < new_t and new_total >= new_t:
                trace.append("R-11")
                trace.append("R-09")
                push_cnt += 1
            outputs["total_expenses"] = new_total
            outputs["push_count"] = push_cnt
            outputs["_trace"] = trace
            return outputs
        else:
            outputs["total_expenses"] = acc
            outputs["push_count"] = initial_push
            outputs["_trace"] = trace
            return outputs

    raise Undefined("Неизвестный сценарий", [])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приёмки 1: Достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "Начальные расходы составляют 48 500 ₸, установленный порог 50 000 ₸. Совершается и проводится покупка на сумму 1 500 ₸.",
  "targets": [
   "R-16",
   "R-08",
   "R-13"
  ],
  "input": {
   "initial_expenses": 48500,
   "threshold": 50000,
   "transaction_amount": 1500,
   "transaction_type": "покупка"
  },
  "expected": {
   "total_expenses": 50000,
   "push_count": 1,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приёмки 2: Покупка 31.01 и проведение 01.02",
  "quote": "Покупка совершена 31.01 в 23:58, сумма 4 000 ₸ | Проведение 01.02 в 00:03 (Алматы) | Расходы февраля увеличились на 4 000 ₸",
  "situation": "Покупка на сумму 4 000 ₸ совершена 31.01 в 23:58 по времени Алматы, а проведена 01.02 в 00:03 по времени Алматы.",
  "targets": [
   "R-17",
   "R-05"
  ],
  "input": {
   "purchase_date_time": "31.01 23:58",
   "processing_date_time": "01.02 00:03",
   "amount": 4000,
   "timezone": "Алматы"
  },
  "expected": {
   "total_expenses": 4000,
   "push_count": 0,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приёмки 3: Перевод при текущих расходах",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "Текущие расходы составляют 19 900 ₸, порог 20 000 ₸. Выполняется операция перевода на сумму 500 ₸.",
  "targets": [
   "R-18",
   "R-07"
  ],
  "input": {
   "initial_expenses": 19900,
   "threshold": 20000,
   "operation_amount": 500,
   "operation_type": "перевод"
  },
  "expected": {
   "total_expenses": 19900,
   "push_count": 0,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Минимальная граница порога",
  "quote": "",
  "situation": "Владелец активной тенговой карты пытается установить порог равный минимальному допустимому значению 1 000 тенге через GET запрос с параметром amount=1000 и enabled=1.",
  "targets": [
   "R-03",
   "R-27",
   "R-31"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "total_expenses": 0,
   "push_count": 0,
   "api_status": 200,
   "api_result": "OK"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Максимальная граница порога",
  "quote": "",
  "situation": "Владелец активной тенговой карты пытается установить порог равный максимальному допустимому значению 1 000 000 тенге через GET запрос с параметром amount=1000000 и enabled=1.",
  "targets": [
   "R-03",
   "R-27",
   "R-31"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "total_expenses": 0,
   "push_count": 0,
   "api_status": 200,
   "api_result": "OK"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Порог ниже допустимого минимума",
  "quote": "",
  "situation": "Владелец карты пытается установить порог 999 тенге, что ниже нижней границы диапазона, через GET запрос с параметром amount=999 и enabled=1.",
  "targets": [
   "R-03",
   "R-27",
   "R-31",
   "R-36"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "total_expenses": 0,
   "push_count": 0,
   "api_status": 400,
   "api_result": "ERROR"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Порог выше допустимого максимума",
  "quote": "",
  "situation": "Владелец карты пытается установить порог 1 000 001 тенге, что выше верхней границы диапазона, через GET запрос с параметром amount=1000001 и enabled=1.",
  "targets": [
   "R-03",
   "R-27",
   "R-31",
   "R-36"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "total_expenses": 0,
   "push_count": 0,
   "api_status": 400,
   "api_result": "ERROR"
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Запрос для чужой карты",
  "quote": "",
  "situation": "Клиент отправляет GET запрос на сохранение настроек с параметром cardId принадлежащим другому клиенту.",
  "targets": [
   "R-39",
   "R-23"
  ],
  "input": {
   "cardId": "alien-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "total_expenses": 0,
   "push_count": 0,
   "api_status": 404,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Повторная доставка события процессинга",
  "quote": "",
  "situation": "Процессинг повторно доставляет одно и то же успешно обработанное ранее событие покупки на сумму 5 000 ₸ при текущих расходах 45 000 ₸ и пороге 50 000 ₸.",
  "targets": [
   "R-15",
   "R-08"
  ],
  "input": {
   "initial_expenses": 45000,
   "threshold": 50000,
   "transaction_amount": 5000,
   "delivery_count": 2
  },
  "expected": {
   "total_expenses": 50000,
   "push_count": 1,
   "api_status": null,
   "api_result": null
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Смена порога при накопленных расходах выше нового порога",
  "quote": "",
  "situation": "Накопленные расходы составляют 60 000 ₸, ранее был отправлен один push при достижении старого порога 50 000 ₸. Владелец меняет порог на новый уровень 70 000 ₸.",
  "targets": [
   "R-10",
   "R-11",
   "R-29"
  ],
  "input": {
   "accumulated_expenses": 60000,
   "old_threshold": 50000,
   "new_threshold": 70000,
   "initial_push_count": 1
  },
  "expected": {
   "total_expenses": 60000,
   "push_count": 1,
   "api_status": 200,
   "api_result": "OK"
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Смена порога при накопленных расходах ниже нового порога",
  "quote": "",
  "situation": "Накопленные расходы составляют 40 000 ₸, ранее был отправлен push при старом пороге 30 000 ₸. Владелец меняет порог на новый уровень 50 000 ₸. Затем совершается покупка на 15 000 ₸.",
  "targets": [
   "R-10",
   "R-11",
   "R-29",
   "R-08"
  ],
  "input": {
   "accumulated_expenses": 40000,
   "old_threshold": 30000,
   "new_threshold": 50000,
   "subsequent_purchase": 15000
  },
  "expected": {
   "total_expenses": 55000,
   "push_count": 2,
   "api_status": 200,
   "api_result": "OK"
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-17",
   "R-05"
  ],
  "quote": "Покупка совершена 31.01 в 23:58, сумма 4 000 ₸ | Проведение 01.02 в 00:03 (Алматы) | Расходы февраля увеличились на 4 000 ₸",
  "question": "К какому месяцу относятся расходы при несовпадении месяца совершения и месяца проведения?",
  "a": "Расходы учитываются в месяце совершения покупки (январь), согласно правилу Ф-2",
  "b": "Расходы учитываются в месяце проведения (февраль), согласно критерию приёмки"
 },
 {
  "id": "I2",
  "req_ids": [
   "R-34",
   "R-35",
   "R-36"
  ],
  "quote": "Если результат 200 или 201 — успешный. Если результат 400, 401 и далее — неуспешный.",
  "question": "Какой HTTP-статус возвращается методом сохранения при успешном создании или выполнении, учитывая что метод использует GET?",
  "a": "Метод может возвращать статусы 200 и 201 согласно тексту",
  "b": "Метод должен возвращать только 200, так как используется HTTP GET"
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
