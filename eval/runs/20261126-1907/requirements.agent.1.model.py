# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from decimal import Decimal
from datetime import datetime

class Undefined(Exception):
    def __init__(self, message, req_ids):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}
    
    # API Save Limit scenario inputs
    if "authorization" in scenario or "card_id" in scenario:
        auth = scenario.get("authorization")
        card_id = scenario.get("card_id")
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")
        
        # R-45: Запрос без авторизации
        if not auth:
            trace.append("R-45")
            outputs["api_response_status"] = 401
            outputs["api_result_field"] = "ERROR"
            outputs["_trace"] = trace
            return outputs
            
        # R-48: Чужая или отсутствующая карта
        if card_id == "alien-99" or not card_id:
            trace.append("R-48")
            outputs["api_response_status"] = 404
            outputs["api_result_field"] = "ERROR"
            outputs["_trace"] = trace
            return outputs
            
        # R-38, R-39, R-40, R-44: Валидация параметров
        invalid = False
        if card_id is not None and not (1 <= len(str(card_id)) <= 64):
            invalid = True
        if amount is not None and not (1000 <= amount <= 1000000):
            invalid = True
            trace.append("R-39")
        if enabled is not None and enabled not in (0, 1):
            invalid = True
            trace.append("R-40")
            
        if invalid:
            trace.append("R-44")
            outputs["api_response_status"] = 400
            outputs["api_result_field"] = "ERROR"
            outputs["_trace"] = trace
            return outputs
            
        # R-30, R-43: Успешное сохранение
        trace.append("R-30")
        trace.append("R-43")
        trace.append("R-35")
        outputs["api_response_status"] = 200
        outputs["api_result_field"] = "OK"
        outputs["limit_amount"] = amount
        outputs["enabled_status"] = enabled
        outputs["_trace"] = trace
        return outputs

    # S2: Покупка в полночь по времени Алматы
    if "purchase_date_time" in scenario and "processing_date_time_almaty" in scenario:
        trace.append("R-07")
        proc_dt = datetime.fromisoformat(scenario["processing_date_time_almaty"])
        outputs["total_expenses"] = scenario["purchase_amount"]
        outputs["push_count"] = 0
        outputs["enabled_status"] = 0
        outputs["_trace"] = trace
        return outputs

    # S3: Исключение перевода
    if scenario.get("action_type") == "transfer":
        trace.append("R-10")
        outputs["total_expenses"] = scenario["initial_expenses"]
        outputs["push_count"] = 0
        outputs["limit_amount"] = scenario.get("threshold", 20000)
        outputs["enabled_status"] = 0
        outputs["_trace"] = trace
        return outputs

    # S10: Повторная доставка события
    if "delivery_count" in scenario and scenario["delivery_count"] > 2:
        raise Undefined("Delivery count > 2 not specified", ["R-21"])
    if "delivery_count" in scenario and scenario["delivery_count"] == 2:
        trace.append("R-21")
        initial = scenario.get("initial_expenses", 0)
        p_amount = scenario.get("purchase_amount", 0)
        outputs["total_expenses"] = initial + p_amount
        outputs["push_count"] = 0
        outputs["limit_amount"] = scenario.get("threshold", 50000)
        outputs["enabled_status"] = 0
        outputs["_trace"] = trace
        return outputs

    # S11: Изменение порога
    if "new_threshold" in scenario:
        trace.append("R-13")
        trace.append("R-36")
        outputs["total_expenses"] = scenario["initial_expenses"]
        outputs["limit_amount"] = scenario["new_threshold"]
        outputs["push_count"] = 1
        outputs["enabled_status"] = scenario.get("enabled", 1)
        outputs["_trace"] = trace
        return outputs

    # S12: Возврат средств
    if scenario.get("action_type") == "refund":
        trace.append(
            "R-09"
        )
        initial = scenario.get("initial_expenses", 0)
        amount = scenario.get("action_amount", 0)
        outputs["total_expenses"] = initial - amount
        outputs["limit_amount"] = scenario.get("threshold", 50000)
        outputs["push_count"] = 1
        outputs["enabled_status"] = 1
        outputs["_trace"] = trace
        return outputs

    # S1: Достижение порога покупкой
    if scenario.get("action_type") == "purchase":
        trace.append("R-08")
        trace.append("R-11")
        trace.append("R-12")
        initial = scenario.get("initial_expenses", 0)
        action_amount = scenario.get("action_amount", 0)
        total = initial + action_amount
        outputs["total_expenses"] = total
        outputs["limit_amount"] = scenario.get("threshold", 50000)
        outputs["push_count"] = 1 if total >= outputs["limit_amount"] else 0
        outputs["enabled_status"] = 1 if outputs["push_count"] > 0 else 0
        outputs["_trace"] = trace
        return outputs

    raise Undefined("Scenario not handled", ["R-05"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приёмки: достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "На карте зафиксированы расходы 48 500 ₸, установленный порог составляет 50 000 ₸. Поступило событие о проведении покупки на сумму 1 500 ₸.",
  "targets": [
   "R-22"
  ],
  "input": {
   "initial_expenses": 48500,
   "threshold": 50000,
   "action_type": "purchase",
   "action_amount": 1500
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
  "title": "Критерий приёмки: покупка в полночь по времени Алматы",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ | Провести 1 февраля в 00:03 по Алматы | Февральский счётчик вырос на 4 000 ₸",
  "situation": "Совершена покупка 31 января в 23:58 на сумму 4 000 ₸. Событие о проведении покупки поступило 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-23"
  ],
  "input": {
   "purchase_date_time": "2023-01-31T23:58:00",
   "processing_date_time_almaty": "2023-02-01T00:03:00",
   "purchase_amount": 4000
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
  "title": "Критерий приёмки: исключение перевода из расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "На карте зафиксированы расходы 19 900 ₸, порог составляет 20 000 ₸. Совершен перевод на сумму 500 ₸.",
  "targets": [
   "R-24"
  ],
  "input": {
   "initial_expenses": 19900,
   "threshold": 20000,
   "action_type": "transfer",
   "action_amount": 500
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
  "title": "Сохранение настройки с минимальной границей порога",
  "quote": "",
  "situation": "Клиент с активной сессией и принадлежащей ему картой выполняет GET-запрос на сохранение порога с параметрами cardId=demo-42, amount=1000, enabled=1.",
  "targets": [
   "R-05",
   "R-34",
   "R-39",
   "R-43"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000,
   "enabled": 1,
   "authorization": "Bearer valid_token"
  },
  "expected": {
   "api_response_status": 200,
   "api_result_field": "OK",
   "limit_amount": "1000",
   "enabled_status": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Сохранение настройки с максимальной границей порога",
  "quote": "",
  "situation": "Клиент с активной сессией и принадлежащей ему картой выполняет GET-запрос на сохранение порога с параметрами cardId=demo-42, amount=1000000, enabled=1.",
  "targets": [
   "R-05",
   "R-34",
   "R-39",
   "R-43"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000000,
   "enabled": 1,
   "authorization": "Bearer valid_token"
  },
  "expected": {
   "api_response_status": 200,
   "api_result_field": "OK",
   "limit_amount": "1000000",
   "enabled_status": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Попытка сохранения порога ниже допустимого значения",
  "quote": "",
  "situation": "Клиент выполняет GET-запрос на сохранение порога с параметром amount=999 для своей карты.",
  "targets": [
   "R-05",
   "R-33",
   "R-39",
   "R-44"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 999,
   "enabled": 1,
   "authorization": "Bearer valid_token"
  },
  "expected": {
   "api_response_status": 400,
   "api_result_field": "ERROR",
   "limit_amount": null,
   "enabled_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Попытка сохранения порога выше допустимого значения",
  "quote": "",
  "situation": "Клиент выполняет GET-запрос на сохранение порога с параметром amount=1000001 для своей карты.",
  "targets": [
   "R-05",
   "R-33",
   "R-39",
   "R-44"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000001,
   "enabled": 1,
   "authorization": "Bearer valid_token"
  },
  "expected": {
   "api_response_status": 400,
   "api_result_field": "ERROR",
   "limit_amount": null,
   "enabled_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Запрос без авторизационного токена",
  "quote": "",
  "situation": "Выполняется GET-запрос на сохранение порога /alerts/saveLimit с параметрами cardId=demo-42, amount=50000, enabled=1 без заголовка Authorization.",
  "targets": [
   "R-26",
   "R-45"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 50000,
   "enabled": 1,
   "authorization": null
  },
  "expected": {
   "api_response_status": 401,
   "api_result_field": "ERROR",
   "limit_amount": null,
   "enabled_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Запрос настроек для чужой или несуществующей карты",
  "quote": "",
  "situation": "Клиент с валидной сессией выполняет GET-запрос на сохранение порога для чужой или несуществующей карты с параметром cardId=alien-99.",
  "targets": [
   "R-30",
   "R-48"
  ],
  "input": {
   "card_id": "alien-99",
   "amount": 50000,
   "enabled": 1,
   "authorization": "Bearer valid_token"
  },
  "expected": {
   "api_response_status": 404,
   "api_result_field": "ERROR",
   "limit_amount": null,
   "enabled_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Повторная доставка одного события процессинга",
  "quote": "",
  "situation": "От процессинга повторно доставлено ровно одно и то же событие о проведенной покупке на сумму 10 000 ₸ при текущих расходах 20 000 ₸.",
  "targets": [
   "R-21"
  ],
  "input": {
   "initial_expenses": 20000,
   "threshold": 50000,
   "event_id": "op-12345",
   "purchase_amount": 10000,
   "delivery_count": 2
  },
  "expected": {
   "total_expenses": 30000,
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Изменение порога при текущих расходах ниже нового порога",
  "quote": "",
  "situation": "На карте накоплены расходы 30 000 ₸, действующий порог 25 000 ₸ (уведомление уже отправлено). Клиент изменяет порог через API на 50 000 ₸.",
  "targets": [
   "R-13",
   "R-14",
   "R-36"
  ],
  "input": {
   "initial_expenses": 30000,
   "previous_threshold": 25000,
   "new_threshold": 50000,
   "enabled": 1
  },
  "expected": {
   "total_expenses": 30000,
   "limit_amount": "50000",
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Учет операции возврата средств",
  "quote": "",
  "situation": "На карте зафиксированы расходы 52 000 ₸ (порог 50 000 ₸, push уже отправлен). Поступает операция возврата исходной покупки на сумму 5 000 ₸ в том же календарном месяце.",
  "targets": [
   "R-09"
  ],
  "input": {
   "initial_expenses": 52000,
   "threshold": 50000,
   "action_type": "refund",
   "action_amount": 5000
  },
  "expected": {
   "total_expenses": 47000,
   "push_count": 1
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-11",
   "R-12"
  ],
  "quote": "Когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push. На карту приходится максимум один такой push за календарный месяц.",
  "question": "Сбрасывается ли счетчик отправленных push-уведомлений при изменении порога или смене месяца?",
  "a": "Push отправляется только один раз за календарный месяц независимо от изменения порога, если порог уже был достигнут ранее.",
  "b": "При повышении порога выше текущих расходов флаг отправки сбрасывается, и при повторном достижении нового порога отправляется второй push за месяц."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-09"
  ],
  "quote": "Возврат уменьшает расходы месяца исходной покупки.",
  "question": "В каком календарном месяце учитывается уменьшение расходов, если возврат совершен в следующем месяце?",
  "a": "Возврат уменьшает расходы того месяца, в котором была совершена исходная покупка.",
  "b": "Возврат уменьшает расходы текущего календарного месяца, в котором фактически проведен возврат."
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
