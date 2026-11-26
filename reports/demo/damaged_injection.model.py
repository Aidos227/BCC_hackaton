# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
class Undefined(Exception):
    def __init__(self, message, req_ids):
        super().__init__(message)
        self.req_ids = req_ids

def run(scenario: dict, interp: dict) -> dict:
    trace = []
    outputs = {}
    
    # API check: Authorization / session (R-17, R-32)
    if "authorization_header" in scenario:
        if scenario.get("authorization_header") is None:
            trace.append("R-17")
            trace.append("R-32")
            outputs["api_response_status"] = 401
            outputs["api_response_body"] = {"message": "Требуется вход"}
            outputs["_trace"] = trace
            return outputs

    # API check: Card ownership (R-18, R-34)
    card_id = scenario.get("cardId") or scenario.get("new_request_cardId")
    if card_id and (card_id.startswith("foreign-") or card_id == "absent"):
        trace.append("R-18")
        trace.append("R-34")
        outputs["api_response_status"] = 404
        outputs["api_response_body"] = {"message": "Карта не найдена"}
        outputs["_trace"] = trace
        return outputs

    # API check: Amount and enabled (R-19, R-22, R-26, R-27, R-31)
    amount = scenario.get("amount")
    if amount is not None:
        if not isinstance(amount, int) or not (1000 <= amount <= 1000000):
            trace.append("R-19")
            trace.append("R-22")
            trace.append("R-26 photochemical")
            trace.append("R-31")
            outputs["api_response_status"] = 400
            outputs[
                "api_response_body"
            ] = {"result": "ERROR", "message": "Проверьте сумму"} if interp.get("I4") == "a" else {"message": "Некорректный запрос"}
            outputs["_trace"] = trace
            return outputs
        else:
            trace.append("R-19")
            trace.append("R-20")
            outputs["api_response_status"] = 200
            outputs["api_response_body"] = {
                "result": "OK",
                "amount": str(amount),
                "enabled": str(scenario.get("enabled", 1))
            }
            outputs["_trace"] = trace
            return outputs

    # Existing setting replacement (R-23)
    if "existing_limit_kzt" in scenario:
        trace.append("R-23")
        outputs["api_response_status"] = 200
        outputs["api_response_body"] = {
            "result": "OK",
            "amount": str(scenario.get("new_request_amount")),
            "enabled": str(scenario.get("new_request_enabled"))
        }
        outputs["_trace"] = trace
        return outputs

    # Transfer exclusion scenario (R-08)
    if "transfer_amount_kzt" in scenario:
        trace.append("R-08")
        if interp.get("I2") == "b":
            raise Undefined("Cannot distinguish transfer from purchase", ["R-08"])
        init_exp = scenario.get("initial_expenses_kzt", 0)
        outputs["expenses_kzt"] = init_exp
        outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    # Purchase threshold scenarios (R-06, R-09, R-10, R-11, R-12, R-16)
    if "action_amount_kzt" in scenario:
        init_exp = scenario.get("initial_expenses_kzt", 0)
        limit = scenario.get(
            "limit_kzt"
        ) or scenario.get("new_limit_kzt") or 50000
        action_amt = scenario.get("action_amount_kzt")
        new_exp = init_exp + action_amt
        trace.append("R-06")

        push_count = 0
        if init_exp < limit and new_exp >= limit:
            trace.append("R-09")
            trace.append("R-10")
            push_count = 1

        outputs["expenses_kzt"] = new_exp
        outputs["push_count"] = push_count
        outputs["_trace"] = trace
        return outputs

    # Subsequent purchase after limit change (R-11, R-12)
    if "subsequent_purchase_amount_kzt" in scenario:
        trace.append("R-11")
        init_exp = scenario.get("initial_expenses_kzt", 0)
        new_limit = scenario.get("new_limit_kzt")
        sub_amt = scenario.get("subsequent_purchase_amount_kzt")
        new_exp = init_exp + sub_amt
        
        push_count = scenario.get("push_sent_before_change", 0)
        if interp.get("I3") == "a":
            if init_exp < new_limit and new_exp >= new_limit:
                trace.append("R-12")
                push_count += 1
        else:
            trace.append("R-12")
            
        outputs["expenses_kzt"] = new_exp
        outputs["push_count"] = push_count
        outputs["_trace"] = trace
        return outputs

    # Duplicate delivery (R-16)
    if "delivery_count" in scenario:
        trace.append("R-16")
        init_exp = scenario.get("initial_expenses_kzt", 0)
        amt = scenario.get("amount_kzt", 0)
        outputs["expenses_kzt"] = init_exp + amt
        outputs["push_count"] = 1
        outputs["_trace"] = trace
        return outputs

    # Date/Month handling (R-05)
    if "purchase_datetime" in scenario:
        trace.append("R-05")
        outputs["expenses_kzt"] = scenario.get("amount_kzt", 0)
        outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    raise Undefined("Unmatched scenario input", [])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "Исходные условия: расходы составляют 48 500 ₸, порог равен 50 000 ₸. Действие: провести покупку на 1 500 ₸.",
  "targets": [
   "R-06",
   "R-09"
  ],
  "input": {
   "initial_expenses_kzt": 48500,
   "limit_kzt": 50000,
   "action_amount_kzt": 1500
  },
  "expected": {
   "expenses_kzt": 50000,
   "push_count": 1,
   "api_response_status": null,
   "api_response_body": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Покупка на стыке месяцев",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ | Провести 1 февраля в 00:03 по Алматы | Февральский счётчик вырос на 4 000 ₸",
  "situation": "Исходные условия: совершение покупки 31 января в 23:58 на сумму 4 000 ₸. Действие: провести покупку 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-05",
   "R-06"
  ],
  "input": {
   "purchase_datetime": "2026-01-31T23:58:00",
   "processing_datetime_almaty": "2026-02-01T00:03:00",
   "amount_kzt": 4000
  },
  "expected": {
   "expenses_kzt": 4000,
   "push_count": 0,
   "api_response_status": null,
   "api_response_body": null
  },
  "lost_facts": [
   "февральскии"
  ]
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Исключение переводов из расходов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "Исходные условия: расходы составляют 19 900 ₸, порог равен 20 000 ₸. Действие: выполнить перевод на 500 ₸.",
  "targets": [
   "R-08"
  ],
  "input": {
   "initial_expenses_kzt": 19900,
   "limit_kzt": 20000,
   "transfer_amount_kzt": 500
  },
  "expected": {
   "expenses_kzt": 19900,
   "push_count": 0,
   "api_response_status": null,
   "api_response_body": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Установка минимального допустимого порога",
  "quote": "",
  "situation": "Держатель активной карты KZT выполняет запрос сохранения настроек через REST API с параметром amount равным 1 000, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-15",
   "R-22",
   "R-26",
   "R-30"
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
  "title": "Установка максимального допустимого порога",
  "quote": "",
  "situation": "Держатель активной карты KZT выполняет запрос сохранения настроек через REST API с параметром amount равным 1 000 000, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-15",
   "R-22",
   "R-26",
   "R-30"
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
  "id": "S6",
  "source": "boundary",
  "title": "Установка порога ниже минимального значения",
  "quote": "",
  "situation": "Держатель активной карты KZT выполняет запрос сохранения настроек через REST API с параметром amount равным 999, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-21",
   "R-22",
   "R-26",
   "R-31"
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
  "id": "S7",
  "source": "boundary",
  "title": "Установка порога выше максимального значения",
  "quote": "",
  "situation": "Держатель активной карты KZT выполняет запрос сохранения настроек через REST API с параметром amount равным 1 000 001, enabled равным 1 и валидным cardId.",
  "targets": [
   "R-03",
   "R-21",
   "R-22",
   "R-26",
   "R-31"
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
  "title": "Повторная доставка идентичного события процессинга",
  "quote": "",
  "situation": "В сервис расходов поступает событие о проведенной покупке на 5 000 ₸. После успешного учета и изменения расходов происходит повторная доставка ровно того же самого события процессинга.",
  "targets": [
   "R-06",
   "R-16"
  ],
  "input": {
   "initial_expenses_kzt": 45000,
   "limit_kzt": 50000,
   "operation_id": "op-12345",
   "amount_kzt": 5000,
   "delivery_count": 2
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Изменение порога при текущих расходах ниже нового порога",
  "quote": "",
  "situation": "Текущие расходы клиента составляют 45 000 ₸, действовал порог 40 000 ₸ (push уже был отправлен). Клиент изменяет порог через API на 50 000 ₸ (накопленные расходы сохраняются и становятся ниже нового порога). Затем совершается новая покупка, увеличивающая расходы до 52 000 ₸.",
  "targets": [
   "R-09",
   "R-11",
   "R-12",
   "R-24"
  ],
  "input": {
   "initial_expenses_kzt": 45000,
   "previous_limit_kzt": 40000,
   "new_limit_kzt": 50000,
   "push_sent_before_change": 1,
   "subsequent_purchase_amount_kzt": 7000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Запрос с недействительной или отсутствующей авторизацией",
  "quote": "",
  "situation": "Пользователь выполняет GET-запрос на метод `/alerts/saveLimit` без заголовка `Authorization` или с недействительным токеном.",
  "targets": [
   "R-15",
   "R-17",
   "R-29",
   "R-32"
  ],
  "input": {
   "authorization_header": null,
   "cardId": "demo-42",
   "amount": 50000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос с указанием идентификатора чужой карты",
  "quote": "",
  "situation": "Авторизованный клиент выполняет GET-запрос на метод `/alerts/saveLimit`, передавая в параметре `cardId` идентификатор карты, которая ему не принадлежит.",
  "targets": [
   "R-15",
   "R-17",
   "R-18",
   "R-29",
   "R-34"
  ],
  "input": {
   "authorization_token": "valid_token",
   "cardId": "foreign-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Повторное сохранение настроек для замены действующей",
  "quote": "",
  "situation": "Клиент уже имеет сохраненную настройку порога 50 000 ₸ и enabled 1. Клиент выполняет повторный запрос на сохранение с новыми параметрами: порог 60 000 ₸ и enabled 0.",
  "targets": [
   "R-15",
   "R-20",
   "R-23",
   "R-30"
  ],
  "input": {
   "existing_limit_kzt": 50000,
   "existing_enabled": 1,
   "new_request_cardId": "demo-42",
   "new_request_amount": 60000,
   "new_request_enabled": 0
  },
  "expected": null,
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-07"
  ],
  "quote": "Возврат уменьшает расходы месяца исходной покупки.",
  "question": "Уменьшает ли возврат накопленные расходы ниже нуля или минимальное значение расходов ограничено нулем?",
  "a": "Расходы могут становиться отрицательными при возврате, превышающем накопленные расходы.",
  "b": "Расходы ограничиваются снизу нулем и не могут быть отрицательными."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-08"
  ],
  "quote": "Переводы и снятие наличных исключаются.",
  "question": "Каким образом система определяет, является ли операция переводом или снятием наличных, если в требованиях к данным хранятся только идентификатор карты, месяц, идентификатор операции, сумма покупки в тиынах, признак отправки и порог в тенге?",
  "a": "Операции фильтруются на стороне процессинга до передачи событий в сервис расходов.",
  "b": "В требованиях к данным отсутствует поле типа операции, поэтому сервис не может отличить покупку от перевода или снятия наличных по сохраненным данным."
 },
 {
  "id": "I3",
  "req_ids": [
   "R-12"
  ],
  "quote": "Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.",
  "question": "Сбрасывается ли счетчик отправленных push-уведомлений за календарный месяц при изменении порога или ограничение 'максимум один такой push за календарный месяц' продолжает действовать?",
  "a": "Счетчик отправленных push сбрасывается или разрешается повторная отправка push при достижении нового порога в том же месяце.",
  "b": "Ограничение максимум один push за календарный месяц сохраняется, и повторный push не отправляется, даже если порог был изменен."
 },
 {
  "id": "I4",
  "req_ids": [
   "R-34"
  ],
  "quote": "Для чужой карты возвращается 404, как и для отсутствующей карты.",
  "question": "Какой именно HTTP-статус должен возвращаться для чужой карты и отсутствующей карты, учитывая, что в тексте упомянут статус 404, а в списке статусных кодов код 404 не имеет отдельного описания?",
  "a": "Возвращается HTTP-статус 404 с сообщением 'Карта не найдена'.",
  "b": "Возвращается HTTP-статус 403 или другой код ошибки доступа, так как в перечне статусов описаны только 200, 400, 401, 403, 500."
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
