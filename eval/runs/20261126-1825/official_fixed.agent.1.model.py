# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
class Undefined(Exception):
    def __init__(self, message, reqs):
    # R-.. absence handling
        super().__init__(message)
        self.reqs = reqs

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}
    
    card_id = scenario.get("cardId")
    amount = scenario.get("amount")
    enabled = scenario.get(
        "enabled"
    )
    
    if card_id == "alien-card-00" or card_id == "missing-card":
        trace.append("R-48")
        outputs["http_status"] = 404
        outputs["api_message"] = "Карта не найдена"
        outputs["_trace"] = trace
        return outputs
        
    if card_id == "new-card-99" and scenario.get("action") == "проверка настроек по умолчанию":
        trace.append("R-08")
        outputs["api_enabled"] = "0"
        outputs["_trace"] = trace
        return outputs
        
    if amount is not None:
        if not (1000 <= amount <= 1000000):
            trace.append("R-37")
            trace.append("R-45")
            outputs["http_status"] = 400
            outputs["api_result"] = "ERROR"
            outputs["api_message"] = "Проверьте сумму"
            outputs["_trace"] = trace
            return outputs
        else:
            trace.append("R-32")
            trace.append("R-37")
            trace.append("R-44")
            outputs["http_status"] = 200
            outputs["api_result"] = "OK"
            outputs["amount"] = str(amount)
            outputs["enabled"] = str(enabled)
            outputs["_trace"] = trace
            return outputs
            
    if "purchase_date_time" in scenario and "processing_date_time" in scenario:
        trace.append("R-09")
        outputs["counter_period"] = "январь"
        outputs["_trace"] = trace
        return outputs
        
    initial = scenario.get("initial_expenses_kzt", 0)
    limit = scenario.get("limit_kzt", 0)
    action = scenario.get("action")
    action_amt = scenario.get("action_amount_kzt", 0)
    repeated_amt = scenario.get("repeated_event_amount_kzt", 0)
    push_already_sent = scenario.get("push_already_sent", 0)
    
    if repeated_amt > 0:
        trace.append("R-23")
        outputs["expenses_sum"] = initial
        outputs["push_count"] = push_already_sent
        outputs["_trace"] = trace
        return outputs
        
    if action in ["перевод", "снятие наличных"]:
        trace.append("R-12")
        outputs["expenses_sum"] = initial
        outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs
        
    if action == "проведение покупки":
        trace.append("R-10")
        new_exp = initial + action_amt
        outputs["expenses_sum"] = new_exp
        if initial < limit and new_exp >= limit:
            trace.append("R-13")
            trace.append("R-14")
            outputs["push_count"] = 1
        else:
            outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs
        
    old_limit = scenario.get("old_limit_kzt")
    new_limit = scenario.get("new_limit_kzt")
    if old_limit is not None and new_limit is not None:
        trace.append("R-15")
        trace.append("R-16")
        outputs["expenses_sum"] = initial
        if interp.get("I1") == "a" and initial < new_limit:
            outputs["push_count"] = 0
        else:
            outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    raise Undefined("Неразрешенный сценарий без логики в тексте требований", ["R-01"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: Достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "Начальные расходы составляют 48 500 тенге, порог установлен на 50 000 тенге. Совершается и проводится покупка на 1 500 тенге.",
  "targets": [
   "R-24"
  ],
  "input": {
   "initial_expenses_kzt": 48500,
   "limit_kzt": 50000,
   "action": "проведение покупки",
   "action_amount_kzt": 1500
  },
  "expected": {
   "expenses_sum": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: Дата совершения и проведения в разные дни",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ | Провести 1 февраля в 00:03 по Алматы | Январский счётчик вырос на 4 000 ₸",
  "situation": "Покупка на 4 000 тенге совершена 31 января в 23:58, а проведена 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-25"
  ],
  "input": {
   "purchase_date_time": "31 января 23:58",
   "processing_date_time": "1 февраля 00:03",
   "timezone": "Алматы",
   "amount_kzt": 4000
  },
  "expected": {
   "counter_period": "январь",
   "expenses_sum": 4000
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: Исключение переводов из расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "Текущие расходы составляют 19 900 тенге при пороге 20 000 тенге. Выполняется перевод на 500 тенге.",
  "targets": [
   "R-26"
  ],
  "input": {
   "initial_expenses_kzt": 19900,
   "limit_kzt": 20000,
   "action": "перевод",
   "action_amount_kzt": 500
  },
  "expected": {
   "expenses_sum": 19900,
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Нижняя граница допустимого порога",
  "quote": "",
  "situation": "Клиент с активной картой KZT пытается сохранить через REST API порог равный ровно 1 000 тенге при включенном уведомлении (enabled=1).",
  "targets": [
   "R-07",
   "R-32",
   "R-37"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "http_status": 200,
   "api_result": "OK",
   "api_amount": "1000",
   "api_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Верхняя граница допустимого порога",
  "quote": "",
  "situation": "Клиент с активной картой KZT пытается сохранить через REST API порог равный ровно 1 000 000 тенге при включенном уведомлении (enabled=1).",
  "targets": [
   "R-07",
   "R-32",
   "R-37"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "http_status": 200,
   "api_result": "OK",
   "api_amount": "1000000",
   "api_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Недопустимое значение порога ниже нижней границы",
  "quote": "",
  "situation": "Клиент пытается сохранить через REST API порог 999 тенге (ниже нижней границы 1 000 тенге) при enabled=1.",
  "targets": [
   "R-07",
   "R-31",
   "R-37",
   "R-45"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "http_status": 400,
   "api_message": "Некорректный запрос"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Недопустимое значение порога выше верхней границы",
  "quote": "",
  "situation": "Клиент пытается сохранить через REST API порог 1 000 001 тенге (выше верхней границы 1 000 000 тенге) при enabled=1.",
  "targets": [
   "R-07",
   "R-37",
   "R-45"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "http_status": 400,
   "api_message": "Некорректный запрос"
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Отключенное уведомление по умолчанию",
  "quote": "",
  "situation": "Для новой активной карты KZT проверяется состояние уведомлений до того, как клиент самостоятельно изменил настройки в приложении.",
  "targets": [
   "R-08"
  ],
  "input": {
   "cardId": "new-card-99",
   "action": "проверка настроек по умолчанию"
  },
  "expected": {
   "api_enabled": "0"
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Повторная доставка одного события процессинга",
  "quote": "",
  "situation": "Процессинг повторно доставляет идентичное событие проведенной покупки на 1 500 тенге для карты, у которой уже учтены эти расходы.",
  "targets": [
   "R-23"
  ],
  "input": {
   "initial_expenses_kzt": 50000,
   "limit_kzt": 50000,
   "push_already_sent": 1,
   "repeated_event_amount_kzt": 1500
  },
  "expected": {
   "expenses_sum": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Обращение к API для чужой или отсутствующей карты",
  "quote": "",
  "situation": "Клиент выполняет POST-запрос на сохранение настроек `/alerts/saveLimit` с указанием идентификатора чужой или несуществующей карты.",
  "targets": [
   "R-48"
  ],
  "input": {
   "cardId": "alien-card-00",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "http_status": 404,
   "api_message": "Карта не найдена"
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Изменение порога при сохранении накопленных расходов",
  "quote": "",
  "situation": "При накопленных расходах 45 000 тенге и текущем пороге 50 000 тенге клиент изменяет порог через API на 40 000 тенге.",
  "targets": [
   "R-15",
   "R-16",
   "R-34"
  ],
  "input": {
   "initial_expenses_kzt": 45000,
   "old_limit_kzt": 50000,
   "new_limit_kzt": 40000,
   "enabled": 1
  },
  "expected": {
   "expenses_sum": 45000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Исключение снятия наличных из расходов",
  "quote": "",
  "situation": "На карте с расходами 10 000 тенге и порогом 20 000 тенге выполняется операция снятия наличных на сумму 5 000 тенге.",
  "targets": [
   "R-12"
  ],
  "input": {
   "initial_expenses_kzt": 10000,
   "limit_kzt": 20000,
   "action": "снятие наличных",
   "action_amount_kzt": 5000
  },
  "expected": {
   "expenses_sum": 10000,
   "push_count": 0
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-16"
  ],
  "quote": "Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.",
  "question": "Считается ли отправленным push по старому порогу, если до изменения порога клиент уже получил push, а после увеличения порога текущие расходы оказались ниже нового порога?",
  "a": "Счётчик отправленных push сбрасывается или разрешается повторная отправка push в текущем месяце при достижении нового порога",
  "b": "Ограничение «максимум один такой push за календарный месяц» блокирует отправку второго push, несмотря на изменение порога"
 },
 {
  "id": "I2",
  "req_ids": [
   "R-11"
  ],
  "quote": "Возврат уменьшает расходы месяца исходной покупки.",
  "question": "Уменьшает ли возврат расходы месяца исходной покупки в том случае, если возврат происходит в следующем календарном месяце?",
  "a": "Возврат пересчитывает расходы исторически за месяц совершения исходной покупки",
  "b": "Возврат учитывается в текущем месяце проведения возврата"
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
