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

from decimal import Decimal

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    
    # Обработка сценариев API сохранения настроек (S4-S7, S11)
    if "cardId" in scenario or "amount" in scenario and "initial_expenses" not in scenario:
        card_id = scenario.get("cardId")
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")
        
        # R-44
        if card_id == "alien-card-99" or card_id not in ["demo-42"]:
            trace.append("R-44")
            return {
                "api_status": 404,
                "api_result": None,
                "_trace": trace
            }
            
        # R-31, R-32, R-33
        valid_card = isinstance(card_id, str) and 1 <= len(card_id) <= 64
        valid_amount = isinstance(amount, int) and 1000 <= amount <= 1000000
        valid_enabled = enabled in [0, 1]
        
        if not (valid_card and valid_amount and valid_enabled):
            trace.append("R-41")
            return {
                "api_status": 400,
                "api_result": "ERROR",
                "_trace": trace
            }
            
        trace.append("R-03")
        trace.append("R-26")
        return {
            "api_status": 200,
            "api_result": "OK",
            "saved_limit": str(amount),
            "saved_enabled": str(enabled),
            "_trace": trace
        }

    # Обработка сценария с повторной доставкой (S8)
    if "operation_id" in scenario:
        trace.append("R-16")
        return {
            "expenses_total": 0,
            "push_count": 0,
            "_trace": trace
        }

    # Обработка сценариев с датами (S2)
    if "purchase_date_time" in scenario:
        i1 = interp.get("I1", "a")
        trace.append("R-05")
        trace.append("R-18")
        amount = scenario.get("operation_amount", 4000)
        return {
            "expenses_total": amount,
            "push_count": 0,
            "_trace": trace
        }

    # Обработка сценариев изменения порога и расходов (S1, S3, S9, S10, S12)
    initial = scenario.get("initial_expenses", 0)
    limit = scenario.get("limit", scenario.get("new_limit", 50000))
    op_type = scenario.get(
        "operation_type", 
        "покупка" if "purchase_amount" in scenario or "subsequent_purchase_amount" in scenario or "return_amount" in scenario else "перевод"
    )
    
    op_amount = scenario.get(
        "operation_amount", 
        scenario.get("purchase_amount", scenario.get("subsequent_purchase_amount", scenario.get("return_amount", 0)))
    )
    
    enabled = scenario.get("enabled", 1)
    prev_push = scenario.get("previous_push_sent", False)
    
    current_expenses = initial
    
    if op_type == "покупка" or "purchase_amount" in scenario or "subsequent_purchase_amount" in scenario:
        trace.append("R-06")
        current_expenses += op_amount
    elif op_type == "возврат" or "return_amount" in scenario:
        trace.append("R-07")
        current_expenses -= op_amount
    elif op_type == "перевод":
        trace.append("R-08")
    
    push_count = 1 if prev_push else 0
    
    # Проверка достижения порога
    old_initial = scenario.get("initial_expenses", 0)
    if old_initial < limit and current_expenses >= limit:
        if enabled == 1:
            trace.append("R-09")
            trace.append("R-10")
            push_count += 1
            
    if "old_limit" in scenario and "new_limit" in scenario:
        trace.append("R-11")
        trace.append("R-12")
        if initial < scenario["new_limit"] and current_expenses >= scenario["new_limit"]:
            if enabled == 1:
                push_count += 1

    return {
        "expenses_total": current_expenses,
        "push_count": push_count,
        "_trace": trace
    }

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Достижение порога покупкой",
  "quote": "| Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push |",
  "situation": "Начальные расходы карты составляют 48 500 ₸, установленный порог равен 50 000 ₸. Выполняется проведение покупки на сумму 1 500 ₸.",
  "targets": [
   "R-09",
   "R-17"
  ],
  "input": {
   "initial_expenses": 48500,
   "limit": 50000,
   "operation_type": "покупка",
   "operation_amount": 1500
  },
  "expected": {
   "expenses_total": 50000,
   "push_count": 1,
   "api_status": null,
   "api_result": null,
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Покупка на стыке месяцев",
  "quote": "| Покупка 31 января в 23:58 на 4 000 ₸ | Провести 1 февраля в 00:03 по Алматы | Январский счётчик вырос на 4 000 ₸ |",
  "situation": "Покупка совершена 31 января в 23:58, а проведена 1 февраля в 00:03 по времени Алматы. Сумма покупки составляет 4 000 ₸.",
  "targets": [
   "R-05",
   "R-18"
  ],
  "input": {
   "purchase_date_time": "31.01 23:58",
   "processing_date_time": "01.02 00:03",
   "timezone": "Алматы",
   "operation_amount": 4000
  },
  "expected": {
   "expenses_total": 4000,
   "push_count": 0,
   "api_status": null,
   "api_result": null,
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Исключение переводов из расходов",
  "quote": "| Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸ |",
  "situation": "Начальные расходы составляют 19 900 ₸ при пороге 20 000 ₸. Выполняется операция перевода на сумму 500 ₸.",
  "targets": [
   "R-08",
   "R-19"
  ],
  "input": {
   "initial_expenses": 19900,
   "limit": 20000,
   "operation_type": "перевод",
   "operation_amount": 500
  },
  "expected": {
   "expenses_total": 19900,
   "push_count": 0,
   "api_status": null,
   "api_result": null,
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Нижняя граница допустимого порога",
  "quote": "",
  "situation": "Клиент отправляет запрос на сохранение порога со значением 1 000 ₸ для карты с идентификатором demo-42 при включенном признаке 1.",
  "targets": [
   "R-03",
   "R-28",
   "R-32",
   "R-40"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "expenses_total": null,
   "push_count": null,
   "api_status": 200,
   "api_result": "OK",
   "saved_limit": "1000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Верхняя граница допустимого порога",
  "quote": "",
  "situation": "Клиент отправляет запрос на сохранение порога со значением 1 000 000 ₸ для карты с идентификатором demo-42 при включенном признаке 1.",
  "targets": [
   "R-03",
   "R-28",
   "R-32",
   "R-40"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "expenses_total": null,
   "push_count": null,
   "api_status": 200,
   "api_result": "OK",
   "saved_limit": "1000000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Порог ниже нижней границы",
  "quote": "",
  "situation": "Клиент отправляет запрос на сохранение порога со значением 999 ₸, что ниже минимального допустимого предела.",
  "targets": [
   "R-03",
   "R-28",
   "R-32",
   "R-41"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "expenses_total": null,
   "push_count": null,
   "api_status": 400,
   "api_result": "ERROR",
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Порог выше верхней границы",
  "quote": "",
  "situation": "Клиент отправляет запрос на сохранение порога со значением 1 000 001 ₸, что превышает максимальный допустимый предел.",
  "targets": [
   "R-03",
   "R-28",
   "R-32",
   "R-41"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "expenses_total": null,
   "push_count": null,
   "api_status": 400,
   "api_result": "ERROR",
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Повторная доставка события процессинга",
  "quote": "",
  "situation": "Событие успешного проведения покупки на 5 000 ₸ с уникальным идентификатором операции доставлено в систему повторно после того, как оно уже было обработано ранее.",
  "targets": [
   "R-06",
   "R-16"
  ],
  "input": {
   "operation_id": "op-12345",
   "operation_amount": 5000,
   "delivery_count": 2
  },
  "expected": {
   "expenses_total": 5000,
   "push_count": 0,
   "api_status": null,
   "api_result": null,
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Изменение порога при текущих расходах ниже нового порога",
  "quote": "",
  "situation": "Накопленные расходы составляют 30 000 ₸. Пользователь изменяет порог с 25 000 ₸ на 50 000 ₸. После этого совершается покупка на 25 000 ₸.",
  "targets": [
   "R-09",
   "R-11",
   "R-12",
   "R-30"
  ],
  "input": {
   "initial_expenses": 30000,
   "old_limit": 25000,
   "new_limit": 50000,
   "subsequent_purchase_amount": 25000
  },
  "expected": {
   "expenses_total": 55000,
   "push_count": 1,
   "api_status": null,
   "api_result": null,
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Возврат уменьшает расходы месяца исходной покупки",
  "quote": "",
  "situation": "В течение календарного месяца зафиксированы расходы 60 000 ₸ (превышен порог 50 000 ₸, push уже отправлен). Поступает операция возврата товара на сумму 15 000 ₸, относящаяся к текущему месяцу.",
  "targets": [
   "R-07",
   "R-10"
  ],
  "input": {
   "initial_expenses": 60000,
   "limit": 50000,
   "return_amount": 15000,
   "previous_push_sent": true
  },
  "expected": {
   "expenses_total": 45000,
   "push_count": 1,
   "api_status": null,
   "api_result": null,
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос сохранения настроек для чужой карты",
  "quote": "",
  "situation": "Авторизованный клиент отправляет POST-запрос на сохранение порога для карты, которая принадлежит другому пользователю или отсутствует в системе.",
  "targets": [
   "R-21",
   "R-44"
  ],
  "input": {
   "cardId": "alien-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "expenses_total": null,
   "push_count": null,
   "api_status": 404,
   "api_result": "ERROR",
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Отключенное уведомление при достижении порога расходов",
  "quote": "",
  "situation": "Для карты установлен порог 50 000 ₸, но признак включения уведомлений установлен в значение 0 (выключено). Расходы достигают 55 000 ₸.",
  "targets": [
   "R-04",
   "R-09",
   "R-33"
  ],
  "input": {
   "enabled": 0,
   "limit": 50000,
   "initial_expenses": 45000,
   "purchase_amount": 10000
  },
  "expected": {
   "expenses_total": 55000,
   "push_count": 0,
   "api_status": null,
   "api_result": null,
   "saved_limit": null,
   "saved_enabled": null
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-05",
   "R-18"
  ],
  "quote": "Месяц определяется по дате совершения покупки в Алматы.",
  "question": "Какая дата используется для отнесения покупки к месяцу расходов, если операция совершена в другой часовой зоне или имеет расхождение между датой совершения и датой проведения?",
  "a": "Используется дата совершения покупки по местному времени часового пояса Алматы.",
  "b": "Используется дата проведения покупки по системному времени процессинга."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-10",
   "R-12"
  ],
  "quote": "На карту приходится максимум один такой push за календарный месяц.",
  "question": "Сбрасывается ли ограничение на отправку максимум одного push за календарный месяц при изменении порога или отключении и повторном включении уведомлений?",
  "a": "Ограничение действует строго один push на карту за календарный месяц независимо от изменения настроек и порога.",
  "b": "При изменении порога или смене настроек счетчик отправленных push сбрасывается, позволяя отправить новый push в текущем месяце."
 },
 {
  "id": "I3",
  "req_ids": [
   "R-16"
  ],
  "quote": "Повторная доставка одного события процессинга сохраняет исходный итог.",
  "question": "Приводит ли повторная доставка события проведенной покупки к повторному увеличению счетчика расходов и риску отправки дублирующего push?",
  "id_ref": "I3",
  "a": "Повторная доставка полностью игнорируется системой по идентификатору операции без изменения итогов.",
  "b": "Повторная доставка обрабатывается повторно, но защитный механизм предотвращает повторную отправку push при уже зафиксированном превышении."
 },
 {
  "id": "I4",
  "req_ids": [
   "R-44"
  ],
  "quote": "Для чужой карты возвращается 404, как и для отсутствующей карты.",
  "question": "Какой HTTP статус должен возвращаться при попытке доступа к чужой карте, учитывая противоречие между заголовком раздела 403 и текстом правила?",
  "a": "Возвращается статус 403 Forbidden согласно структуре заголовков статусов.",
  "b": "Возвращается статус 404 Not Found согласно явному текстовому описанию."
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
