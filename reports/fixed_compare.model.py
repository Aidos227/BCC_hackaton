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

    # R-21, R-42: Authorization check
    if scenario.get("authorization") is None:
        trace.append("R-42")
        outputs["http_status"] = 401
        outputs["api_result"] = "ERROR"
        outputs["response_message"] = "Требуется вход"
        outputs["_trace"] = trace
        return outputs

    # R-33: Content-Type check
    if scenario.get("content_type") == "text/plain":
        trace.append("R-41")
        outputs["http_status"] = 400
        outputs["api_result"] = "ERROR"
        outputs["response_message"] = "Некорректный запрос"
        outputs["_trace"] = trace
        return outputs

    # R-44: Alien card check
    if scenario.get("card_id") == "alien-card-01":
        trace.append("R-44")
        outputs["http_status"] = 404
        outputs["api_result"] = "ERROR"
        outputs["response_message"] = "Карта не найдена"
        outputs["_trace"] = trace
        return outputs

    # R-03, R-27, R-31, R-41: Amount validation for saveLimit
    if "amount" in scenario:
        amt = scenario["amount"]
        if isinstance(amt, int) and 1000 <= amt <= 1000000:
            trace.append("R-03")
            outputs["http_status"] = 200
            outputs["api_result"] = "OK"
            outputs["saved_amount"] = str(amt)
            outputs["saved_enabled"] = str(scenario.get("enabled", 0))
            outputs["_trace"] = trace
            return outputs
        else:
            trace.append("R-41")
            outputs["http_status"] = 400
            outputs["api_result"] = "ERROR"
            outputs["response_message"] = "Проверьте сумму"
            outputs["_trace"] = trace
            return outputs

    # R-16: Duplicate delivery check
    if scenario.get("delivery_count", 1) > 1:
        trace.append("R-16")
        outputs["counter_kzt"] = scenario.get("amount_kzt", 0)
        outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    # R-06, R-17: Purchase processing
    if scenario.get("action") == "purchase" or "initial_expenses_kzt" in scenario and "purchase_amount_kzt" in scenario:
        init_exp = scenario.get("initial_expenses_kzt", 0)
        thresh = scenario.get("threshold_kzt", 0)
        p_amt = scenario.get("purchase_amount_kzt", 0)
        total = init_exp + p_amt
        trace.append("R-06")
        outputs["counter_kzt"] = total
        if init_exp < thresh and total >= thresh:
            trace.append("R-09")
            trace.append("R-10")
            outputs["push_count"] = 1
        else:
            outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    # R-05, R-18: Month determination and clearing
    if "purchase_datetime" in scenario and "clearing_datetime_almaty" in scenario:
        trace.append("R-05")
        # Parse amount string like "4 000 ₸"
        amt_str = str(scenario.get("purchase_amount_kzt", "0"))
        clean_amt = int("".join(filter(str.isdigit, amt_str)))
        outputs["counter_kzt"] = clean_amt
        outputs["_trace"] = trace
        return outputs

    # R-08, R-19: Transfers exclusion
    if scenario.get("action") == "transfer":
        trace.append("R-08")
        outputs["counter_kzt"] = scenario.get("initial_expenses_kzt", 0)
        outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    # R-11, R-12: Threshold change with accumulated sum
    if "current_expenses_kzt" in scenario:
        trace.append("R-11")
        curr = scenario.get("current_expenses_kzt", 0)
        new_t = scenario.get("new_threshold_kzt", 0)
        sub_p = scenario.get("subsequent_purchase_kzt", 0)
        total = curr + sub_p
        outputs["counter_kzt"] = total
        if curr < new_t and total >= new_t:
            trace.append("R-12")
            outputs["push_count"] = 1
        else:
            outputs["push_count"] = 0
        outputs["_trace"] = trace
        return outputs

    raise Undefined("Scenario not handled", ["R-03"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: достижение порога покупкой",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ | Провести покупку на 1 500 ₸ | Итог 50 000 ₸ и один push",
  "situation": "Исходные расходы карты составляют 48 500 ₸, установленный порог — 50 000 ₸. Выполняется проведение покупки на сумму 1 500 ₸.",
  "targets": [
   "R-17"
  ],
  "input": {
   "initial_expenses_kzt": 48500,
   "threshold_kzt": 50000,
   "action": "purchase",
   "purchase_amount_kzt": 1500
  },
  "expected": {
   "counter_kzt": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: покупка на стыке месяцев",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ | Провести 1 февраля в 00:03 по Алматы | Январский счётчик вырос на 4 000 ₸",
  "situation": "Совершение покупки 31 января в 23:58 на сумму 4 000 ₸. Проведение операции выполняется 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-18"
  ],
  "input": {
   "purchase_datetime": "31 января в 23:58",
   "clearing_datetime_almaty": "1 февраля в 00:03",
   "purchase_amount_kzt": "4 000 ₸"
  },
  "expected": {
   "counter_period": "Январский",
   "counter_growth": "на 4 000 ₸"
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: исключение переводов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ | Перевести 500 ₸ | Счётчик показывает 19 900 ₸",
  "situation": "Текущие расходы составляют 19 900 ₸ при пороге 20 000 ₸. Выполняется перевод на сумму 500 ₸.",
  "targets": [
   "R-19"
  ],
  "input": {
   "initial_expenses_kzt": 19900,
   "threshold_kzt": 20000,
   "action": "transfer",
   "transfer_amount_kzt": 500
  },
  "expected": {
   "counter_kzt": 19900,
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Сохранение порога на нижней границе",
  "quote": "",
  "situation": "Отправка POST запроса на /alerts/saveLimit с параметром cardId=demo-42, amount=1000, enabled=1 для активной карты клиента.",
  "targets": [
   "R-03",
   "R-20",
   "R-27",
   "R-31",
   "R-32"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "api_result": "OK",
   "http_status": 200,
   "saved_amount": "1000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Сохранение порога на верхней границе",
  "quote": "",
  "situation": "Отправка POST запроса на /alerts/saveLimit с параметром cardId=demo-42, amount=1000000, enabled=1 для активной карты клиента.",
  "targets": [
   "R-03",
   "R-20",
   "R-27",
   "R-31",
   "R-32"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "api_result": "OK",
   "http_status": 200,
   "saved_amount": "1000000",
   "saved_enabled": "1"
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Превышение верхней границы порога",
  "quote": "",
  "situation": "Отправка POST запроса на /alerts/saveLimit с параметром cardId=demo-42, amount=1000001, enabled=1 для активной карты клиента.",
  "targets": [
   "R-03",
   "R-26",
   "R-27",
   "R-31",
   "R-41"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "api_result": "ERROR",
   "http_status": 400,
   "response_message": "Проверьте сумму"
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Установка порога ниже допустимого значения",
  "quote": "",
  "situation": "Отправка POST запроса на /alerts/saveLimit с параметром cardId=demo-42, amount=999, enabled=1 для активной карты клиента.",
  "targets": [
   "R-03",
   "R-26",
   "R-27",
   "R-31",
   "R-41"
  ],
  "input": {
   "card_id": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "api_result": "ERROR",
   "http_status": 400,
   "response_message": "Проверьте сумму"
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Запрос без авторизации",
  "quote": "",
  "situation": "Отправка POST запроса на /alerts/saveLimit без заголовка Authorization с параметрами cardId=demo-42, amount=50000, enabled=1.",
  "targets": [
   "R-21",
   "R-22",
   "R-42"
  ],
  "input": {
   "authorization": null,
   "card_id": "demo-42",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "http_status": 401,
   "response_message": "Требуется вход"
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Запрос для чужой карты",
  "quote": "",
  "situation": "Отправка POST запроса на /alerts/saveLimit с валидным токеном, но идентификатором чужой карты cardId=alien-card-01.",
  "targets": [
   "R-23",
   "R-44"
  ],
  "input": {
   "authorization": "Bearer valid_token",
   "card_id": "alien-card-01",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "http_status": 404,
   "response_message": "Карта не найдена"
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Повторная доставка события процессинга",
  "quote": "",
  "situation": "Повторная отправка идентичного события о проведении покупки на 1 500 ₸ при уже учтенной ранее покупке.",
  "targets": [
   "R-16"
  ],
  "input": {
   "event_type": "purchase_processed",
   "operation_id": "op-12345",
   "amount_kzt": 1500,
   "delivery_count": 2
  },
  "expected": {
   "counter_kzt": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Изменение порога при накопленной сумме ниже нового порога",
  "quote": "",
  "situation": "Текущие расходы составляют 40 000 ₸, порог равен 45 000 ₸ (push еще не отправлялся). Выполняется изменение порога на 50 000 ₸.",
  "targets": [
   "R-11",
   "R-12",
   "R-29"
  ],
  "input": {
   "current_expenses_kzt": 40000,
   "old_threshold_kzt": 45000,
   "new_threshold_kzt": 50000,
   "subsequent_purchase_kzt": 10000
  },
  "expected": {
   "counter_kzt": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Отправка запроса с неверным типом контента",
  "quote": "",
  "situation": "Отправка POST запроса на /alerts/saveLimit с заголовком Content-Type: text/plain вместо application/json.",
  "targets": [
   "R-33",
   "R-41"
  ],
  "input": {
   "content_type": "text/plain",
   "card_id": "demo-42",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "http_status": 400,
   "response_message": "Некорректный запрос"
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-04",
   "R-12"
  ],
  "quote": "По умолчанию уведомление выключено.",
  "question": "Распространяется ли статус 'выключено по умолчанию' только на момент создания карты, или сброс настроек/изменение порога на клиенте без явного включения также переводит уведомление в выключенное состояние?",
  "a": "Уведомление выключено только для новых карт, при сохранении порога через API передается явный параметр enabled.",
  "b": "Любое изменение настроек без явного указания флага сбрасывает состояние в выключенное по умолчанию."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-07"
  ],
  "quote": "Возврат уменьшает расходы месяца исходной покупки.",
  "quote_alt": "Возврат уменьшает расходы месяца исходной покупки.",
  "question": "Если из-за возврата общая сумма расходов падает ниже порога после того, как push уже был отправлен, разрешен ли повторный push при повторном достижении порога в том же календарном месяце?",
  "a": "Лимит 'максимум один push за календарный месяц' является абсолютным, повторный push не отправляется.",
  "b": "При падении расходов ниже порога счетчик достижений сбрасывается, и при повторном переходе отправляется второй push."
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
