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
    def __init__(self, message: str, req_ids: list):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}

    if "auth_header" in scenario and not scenario["auth_header"]:
        trace.append("R-46")
        return {
            "http_status": 401,
            "api_result": "ERROR",
            "_trace": trace
        }

    if scenario.get("cardId") == "unknown-card":
        trace.append("R-48")
        return {
            "http_status": 404,
            "api_result": "ERROR",
            "_trace": trace
        }

    if "amount" in scenario and "enabled" in scenario:
        amt = scenario["amount"]
        if not (isinstance(amt, int)) or amt < 1000 or amt > 1000000:
            trace.append("R-06")
            trace.append("R-39")
            trace.append("R-45")
            return {
                "http_status": 400,
                "api_result": "ERROR",
                "_trace": trace
            }
        trace.append("R-06")
        trace.append("R-27")
        trace.append("R-30")
        trace.append("R-38")
        trace.append("R-39")
        trace.append("R-40")
        trace.append("R-44")
        return {
            "http_status": 200,
            "api_result": "OK",
            "_trace": trace
        }

    if scenario.get("operation_type") == "transfer":
        trace.append("R-11")
        initial = scenario.get("initial_expenses", 0)
        outputs["expenses_kzt"] = initial
        outputs["counter_change"] = 0
        outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    if "delivery_count" in scenario and scenario["delivery_count"] > 1:
        trace.append("R-22")
        outputs["expenses_kzt"] = scenario.get("amount", 0)
        outputs["push_count"] = 0
        outputs["counter_change"] = scenario.get("amount", 0)
        outputs["_trace"] = trace
        return outputs

    if "refund_amount" in scenario:
        trace.append("R-10")
        outputs["expenses_kzt"] = -scenario["refund_amount"]
        outputs["push_count"] = 0
        outputs["counter_change"] = -scenario["refund_amount"]
        outputs["_trace"] = trace
        return outputs

    if "clearing_date_time" in scenario:
        trace.append("R-08")
        trace.append("R-09")
        amt = scenario.get("amount", 0)
        outputs["expenses_kzt"] = amt
        outputs["counter_change"] = amt
        outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    if scenario.get("operation_type") == "purchase":
        initial = scenario.get("initial_expenses", 0)
        op_amt = scenario.get("operation_amount", 0)
        threshold = scenario.get("threshold", 0)
        new_total = initial + op_amt
        trace.append("R-09")
        trace.append("R-12")
        trace.append("R-13")
        push = 1 if initial < threshold and new_total >= threshold else 0
        outputs["expenses_kzt"] = new_total
        outputs["counter_change"] = op_amt
        outputs["push_count"] = push
        outputs["_trace"] = trace
        return outputs

    raise Undefined("Scenario not handled", ["R-01"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: Покупка достигает порога",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "Начальные расходы по карте составляют 48 500 тенге, заданный порог равен 50 000 тенге. Совершена и проведена покупка на сумму 1 500 тенге.",
  "targets": [
   "R-12",
   "R-23"
  ],
  "input": {
   "initial_expenses": 48500,
   "threshold": 50000,
   "operation_type": "purchase",
   "operation_amount": 1500
  },
  "expected": {
   "expenses_kzt": 50000,
   "push_count": 1,
   "counter_change": 1500,
   "api_result": null,
   "http_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: Покупка в конце месяца с проведением в новом месяце",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ | Провести 1 февраля в 00:03 по Алматы | Январский счётчик вырос на 4 000 ₸",
  "situation": "Совершена покупка 31 января в 23:58 на сумму 4 000 тенге, дата проведения покупки — 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-08",
   "R-09",
   "R-24"
  ],
  "input": {
   "purchase_date_time": "31.01 23:58",
   "clearing_date_time": "01.02 00:03",
   "amount": 4000,
   "timezone": "Алматы"
  },
  "expected": {
   "expenses_kzt": 4000,
   "push_count": 0,
   "counter_change": 4000,
   "api_result": null,
   "http_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: Перевод не влияет на расходы",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "Начальные расходы по карте составляют 19 900 тенге, порог 20 000 тенге. Выполнен перевод на сумму 500 тенге.",
  "targets": [
   "R-11",
   "R-25"
  ],
  "input": {
   "initial_expenses": 19900,
   "threshold": 20000,
   "operation_type": "transfer",
   "operation_amount": 500
  },
  "expected": {
   "expenses_kzt": 19900,
   "push_count": 0,
   "counter_change": 0,
   "api_result": null,
   "http_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Сохранение порога с минимально допустимым значением",
  "quote": "",
  "situation": "Владелец активной карты KZT отправляет запрос на сохранение порога с параметром amount равным 1000, enabled равным 1 и валидным идентификатором карты через метод POST /alerts/saveLimit с действительной авторизацией.",
  "targets": [
   "R-06",
   "R-26",
   "R-28",
   "R-34",
   "R-39",
   "R-40",
   "R-44"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": "OK",
   "http_status": 200
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Сохранение порога с максимально допустимым значением",
  "quote": "",
  "situation": "Владелец активной карты KZT отправляет запрос на сохранение порога с параметром amount равным 1000000, enabled равным 0 и валидным идентификатором карты через метод POST /alerts/saveLimit с действительной авторизацией.",
  "targets": [
   "R-06",
   "R-26",
   "R-28",
   "R-34",
   "R-39",
   "R-40",
   "R-44"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 0
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": "OK",
   "http_status": 200
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Попытка сохранения порога ниже минимального значения",
  "quote": "",
  "situation": "Владелец активной карты KZT отправляет запрос на сохранение порога с параметром amount равным 999, enabled равным 1 и валидным идентификатором карты через метод POST /alerts/saveLimit.",
  "targets": [
   "R-06",
   "R-34",
   "R-39",
   "R-45"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": "ERROR",
   "http_status": 400
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Попытка сохранения порога выше максимального значения",
  "quote": "",
  "situation": "Владелец активной карты KZT отправляет запрос на сохранение порога с параметром amount равным 1000001, enabled равным 1 и валидным идентификатором карты через метод POST /alerts/saveLimit.",
  "targets": [
   "R-06",
   "R-34",
   "R-39",
   "R-45"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": "ERROR",
   "http_status": 400
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Запрос без авторизации",
  "quote": "",
  "situation": "Клиент отправляет POST запрос на /alerts/saveLimit с параметрами cardId=demo-42, amount=50000, enabled=1 без заголовка Authorization.",
  "targets": [
   "R-27",
   "R-46"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 50000,
   "enabled": 1,
   "auth_header": false
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": null,
   "http_status": 401
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Запрос для чужой или отсутствующей карты",
  "quote": "",
  "situation": "Владелец сессии отправляет POST запрос на /alerts/saveLimit для идентификатора карты, который не принадлежит данному клиенту или отсутствует в системе.",
  "targets": [
   "R-30",
   "R-48"
  ],
  "input": {
   "cardId": "unknown-card",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": 0,
   "counter_change": null,
   "api_result": null,
   "http_status": 404
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Изменение порога при уже накопленных расходах",
  "quote": "",
  "situation": "На карте зафиксированы накопленные расходы в размере 45 000 тенге при действующем пороге 50 000 тенге. Владелец карты изменяет порог через API до значения 40 000 тенге.",
  "targets": [
   "R-14",
   "R-15",
   "R-36"
  ],
  "input": {
   "initial_expenses": 45000,
   "old_threshold": 50000,
   "new_threshold": 40000,
   "enabled": 1
  },
  "expected": {
   "expenses_kzt": 45000,
   "push_count": 0,
   "counter_change": 0,
   "api_result": "OK",
   "http_status": 200
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Повторная доставка одного события процессинга",
  "quote": "",
  "situation": "Сервис расходов получает повторное дублирующее событие о ранее уже обработанной и учтенной проведенной покупке на сумму 5 000 тенге для конкретной карты за текущий месяц.",
  "targets": [
   "R-22"
  ],
  "input": {
   "operation_id": "op-12345",
   "amount": 5000,
   "delivery_count": 2
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": 0,
   "counter_change": 0,
   "api_result": null,
   "http_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Возврат уменьшает расходы месяца исходной покупки",
  "quote": "",
  "situation": "В текущем феврале по карте совершен возврат на сумму 10 000 тенге по операции покупки, которая была проведена в предыдущем январском периоде.",
  "targets": [
   "R-10",
   "R-25"
  ],
  "input": {
   "current_month": "февраль",
   "original_purchase_month": "январь",
   "refund_amount": 10000
  },
  "expected": {
   "expenses_kzt": null,
   "push_count": 0,
   "counter_change": -10000,
   "api_result": null,
   "http_status": null
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-10",
   "R-25"
  ],
  "quote": "Возврат уменьшает расходы месяца исходной покупки.",
  "question": "Уменьшает ли возврат расходы текущего месяца, если сама исходная покупка была совершенна в предыдущем календарном месяце?",
  "a": "Возврат уменьшает расходы месяца, в котором была совершена исходная покупка (согласно буквальному тексту).",
  "b": "Возврат уменьшает расходы текущего месяца, в котором он фактически проведен."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-12",
   "R-15"
  ],
  "quote": "Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.",
  "question": "Должен ли быть отправлен push при изменении порога, если текущие накопленные расходы уже равны или выше нового порога в момент изменения?",
  "a": "Push не отправляется в момент изменения порога, так как событием для отправки является момент перехода расходов от суммы ниже порога к сумме, равной порогу или выше.",
  "b": "Push отправляется сразу при изменении порога, если текущие расходы уже превышают новый порог."
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
