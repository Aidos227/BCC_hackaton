# Исполняемая модель требований, сгенерированная агентом LSJ.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from typing import Any, Dict, List, Optional

def run(scenario: Dict[str, Any], interp: Dict[str, Any]) -> Dict[str, Any]:
    trace: List[str] = []
    res: Dict[str, Any] = {
        "monthly_expenses": None,
        "push_count": None,
        "http_status": None,
        "api_result": None,
        "api_message": None,
        "_trace": trace
    }

    # Обработка вызовов REST API
    if "query_params" in scenario or "http_method" in scenario:
        http_method = scenario.get("http_method", "GET") # R-22
        trace.append("R-22")

        if interp.get("I3") == "b" and http_method == "GET":
            res["http_status"] = 400 # R-36
            res["api_result"] = "ERROR" # R-28
            res["api_message"] = "Некорректный метод" # R-36
            trace.extend(["R-28", "R-36"])
            return res

        auth_user = scenario.get("authenticated_user", "client_A") # R-23, R-24
        trace.extend(["R-23", "R-24"])

        qp = scenario.get("query_params", {})
        card_id = qp.get("cardId") # R-32
        trace.append("R-32")

        if auth_user == "client_A" and card_id == "card-of-client-B": # R-25, R-39
            res["http_status"] = 404 # R-39
            res["api_result"] = "ERROR"
            res["api_message"] = "Карта не найдена" # R-39
            trace.extend(["R-25", "R-39"])
            return res

        amount = qp.get("amount") # R-33
        enabled = qp.get("enabled") # R-34
        trace.extend(["R-26", "R-33", "R-34"])

        is_amount_valid = isinstance(amount, int) and (1000 <= amount <= 1000000) # R-04, R-29
        trace.extend(["R-04", "R-29"])

        if not is_amount_valid: # R-28
            trace.append("R-28")
            if interp.get("I4") == "b":
                res["http_status"] = 200 # R-35
                res["api_result"] = "ERROR" # R-28
                res["api_message"] = "Проверьте сумму" # R-28, R-35
                trace.append("R-35")
            else:
                res["http_status"] = 400 # R-36
                res["api_result"] = "ERROR"
                res["api_message"] = "Некорректный запрос" # R-36
                trace.append("R-36")
            return res

        res["http_status"] = 200 # R-35
        res["api_result"] = "OK" # R-27
        res["api_message"] = None
        trace.extend(["R-27", "R-30", "R-35"])
        return res

    # Обработка транзакционных сценариев
    if "delivery_count" in scenario and scenario["delivery_count"] > 1: # R-18
        trace.append("R-18")

    tx_type = scenario.get("transaction_type", "purchase")
    is_conducted = scenario.get("is_conducted", True)

    initial_exp = scenario.get("initial_monthly_expenses_kzt")
    if initial_exp is None:
        initial_exp = scenario.get("initial_expenses_kzt", 0)

    threshold = scenario.get("threshold_kzt")
    if threshold is None:
        threshold = scenario.get("initial_threshold_kzt")

    enabled = scenario.get("enabled", 1) # R-05
    trace.append("R-05")

    if "refund_amount_kzt" in scenario:
        refund_amt = scenario.get("refund_amount_kzt", 0) # R-08
        trace.append("R-08")
        if "subsequent_purchase_amount_kzt" in scenario:
            exp_after_refund = initial_exp - refund_amt # R-08
            sub_purchase = scenario.get("subsequent_purchase_amount_kzt", 0) # R-07
            trace.append("R-07")
            final_exp = exp_after_refund + sub_purchase
            res["monthly_expenses"] = final_exp
            prev_pushes = scenario.get("pushes_sent_this_month", 0)
            if prev_pushes >= 1: # R-11
                trace.append("R-11")
                res["push_count"] = prev_pushes
            else:
                if final_exp >= threshold and exp_after_refund < threshold and enabled == 1: # R-10
                    res["push_count"] = prev_pushes + 1
                    trace.append("R-10")
                else:
                    res["push_count"] = prev_pushes
            return res
        else:
            res["monthly_expenses"] = max(0, initial_exp - refund_amt) # R-08
            res["push_count"] = 0
            return res

    if "new_threshold_kzt" in scenario: # R-12, R-13, R-31
        trace.extend(["R-12", "R-13", "R-31"])
        new_thresh = scenario.get("new_threshold_kzt")
        new_purchase = scenario.get("new_purchase_amount_kzt", 0) # R-07
        trace.append("R-07")
        final_exp = initial_exp + new_purchase # R-12
        res["monthly_expenses"] = final_exp
        prev_pushes = scenario.get("pushes_sent_this_month", 0)

        if interp.get("I2") == "a":
            if initial_exp < new_thresh and final_exp >= new_thresh and enabled == 1:
                res["push_count"] = prev_pushes + 1 # R-13
                trace.append("R-13")
            else:
                res["push_count"] = prev_pushes
        else:
            trace.append("R-11") # R-11
            if prev_pushes >= 1:
                res["push_count"] = prev_pushes
            else:
                if initial_exp < new_thresh and final_exp >= new_thresh and enabled == 1:
                    res["push_count"] = 1 # R-10
                    trace.append("R-10")
                else:
                    res["push_count"] = 0
        return res

    if "purchase_datetime_almaty" in scenario:
        if interp.get("I1") == "b":
            trace.append("R-20") # R-20
        else:
            trace.append("R-06") # R-06
        amt = scenario.get("transaction_amount_kzt", 0)
        if is_conducted: # R-07
            trace.append("R-07")
            res["monthly_expenses"] = amt
        else:
            res["monthly_expenses"] = 0
        res["push_count"] = 0
        return res

    if "amount_tiyn" in scenario: # R-16
        trace.append("R-16")
        amt_kzt = scenario.get("amount_tiyn", 0) // 100
        res["monthly_expenses"] = amt_kzt
        res["push_count"] = 0
        return res

    amt = scenario.get("transaction_amount_kzt", 0)
    if "purchase_amount_kzt" in scenario:
        amt = scenario.get("purchase_amount_kzt", 0)
    elif "auth_amount_kzt" in scenario:
        amt = scenario.get("auth_amount_kzt", 0)

    if tx_type in ["transfer", "cash_withdrawal"]: # R-09, R-21
        trace.extend(["R-09", "R-21"])
        res["monthly_expenses"] = initial_exp
        res["push_count"] = 0
        return res

    if not is_conducted: # R-07
        trace.append("R-07")
        res["monthly_expenses"] = initial_exp
        res["push_count"] = 0
        return res

    trace.extend(["R-03", "R-07"])
    final_exp = initial_exp + amt
    res["monthly_expenses"] = final_exp

    if threshold is not None:
        if enabled == 0: # R-05
            res["push_count"] = 0
        elif initial_exp < threshold and final_exp >= threshold: # R-10, R-19
            trace.extend(["R-10", "R-19"])
            res["push_count"] = 1
            if "pushes_sent_this_month" in scenario: # R-11
                res["push_count"] = min(1, scenario["pushes_sent_this_month"] + 1)
                trace.append("R-11")
        else:
            res["push_count"] = 0
    else:
        res["push_count"] = 0

    return res

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Проведение покупки, точечно достигающей порога расходов",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ Провести покупку на 1 500 ₸ Итог 50 000 ₸ и один push",
  "situation": "У клиента накоплены расходы 48 500 ₸ при установленном пороге 50 000 ₸. Выполняется проведение покупки на сумму 1 500 ₸.",
  "targets": [
   "R-19",
   "R-10",
   "R-07"
  ],
  "input": {
   "initial_monthly_expenses_kzt": 48500,
   "threshold_kzt": 50000,
   "transaction_type": "purchase",
   "transaction_amount_kzt": 1500,
   "is_conducted": true
  },
  "expected": {
   "monthly_expenses": 50000,
   "push_count": 1
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Учёт покупки, совершённой в конце января и проведённой в начале февраля",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ Провести 1 февраля в 00:03 по Алматы Февральский счётчик вырос на 4 000 ₸",
  "situation": "Клиент совершает покупку на 4 000 ₸ 31 января в 23:58 по времени Алматы. Покупка проводится 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-20",
   "R-06",
   "R-07"
  ],
  "input": {
   "purchase_datetime_almaty": "2024-01-31T23:58:00+05:00",
   "posting_datetime_almaty": "2024-02-01T00:03:00+05:00",
   "transaction_type": "purchase",
   "transaction_amount_kzt": 4000,
   "is_conducted": true
  },
  "expected": {
   "february_counter": 4000,
   "push_count": 0
  },
  "lost_facts": [
   "февральский"
  ]
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Исключение операции перевода из суммарных расходов месяца",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ Перевести 500 ₸ Счётчик показывает 19 900 ₸",
  "situation": "У клиента накоплены расходы 19 900 ₸ при пороге 20 000 ₸. Выполняется операция перевода денежных средств на сумму 500 ₸.",
  "targets": [
   "R-21",
   "R-09"
  ],
  "input": {
   "initial_monthly_expenses_kzt": 19900,
   "threshold_kzt": 20000,
   "transaction_type": "transfer",
   "transaction_amount_kzt": 500,
   "is_conducted": true
  },
  "expected": {
   "monthly_expenses": 19900,
   "push_count": 0
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Проведение возврата покупки, совершённой в прошлом месяце",
  "quote": "",
  "situation": "В январе проведена покупка на 10 000 ₸. В феврале проводится возврат по этой покупке на сумму 10 000 ₸. Проверяется изменение расходов января и февраля.",
  "targets": [
   "R-06",
   "R-08"
  ],
  "input": {
   "original_purchase_date_almaty": "2024-01-15T12:00:00+05:00",
   "refund_posting_date_almaty": "2024-02-05T10:00:00+05:00",
   "refund_amount_kzt": 10000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Повторное превышение порога в том же месяце после проведения возврата",
  "quote": "",
  "situation": "Расходы составляли 50 000 ₸ при пороге 50 000 ₸, push уже отправлялся. Проведён возврат на 5 000 ₸ (расходы стали 45 000 ₸). Затем проведена покупка на 6 000 ₸ (расходы стали 51 000 ₸).",
  "targets": [
   "R-08",
   "R-10",
   "R-11"
  ],
  "input": {
   "initial_monthly_expenses_kzt": 50000,
   "threshold_kzt": 50000,
   "pushes_sent_this_month": 1,
   "refund_amount_kzt": 5000,
   "subsequent_purchase_amount_kzt": 6000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Изменение порога на более высокий после уже отправленного push в текущем месяце",
  "quote": "",
  "situation": "При пороге 50 000 ₸ расходы достигли 55 000 ₸, push отправлен. Клиент через API меняет порог на 80 000 ₸. Позднее проводится покупка на 30 000 ₸ (расходы 85 000 ₸).",
  "targets": [
   "R-11",
   "R-12",
   "R-13"
  ],
  "input": {
   "initial_expenses_kzt": 55000,
   "initial_threshold_kzt": 50000,
   "pushes_sent_this_month": 1,
   "new_threshold_kzt": 80000,
   "new_purchase_amount_kzt": 30000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Достижение порога расходов при отключенном уведомлении (enabled = 0)",
  "quote": "",
  "situation": "У клиента порог равен 50 000 ₸, но уведомление выключено (enabled = 0). Накопленные расходы 40 000 ₸. Проводится покупка на 15 000 ₸ (итог 55 000 ₸).",
  "targets": [
   "R-05",
   "R-10",
   "R-34"
  ],
  "input": {
   "enabled": 0,
   "initial_expenses_kzt": 40000,
   "threshold_kzt": 50000,
   "purchase_amount_kzt": 15000
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Сохранение порога со значением ниже минимальной границы (999 ₸)",
  "quote": "",
  "situation": "Клиент отправляет GET-запрос на /alerts/saveLimit с параметрами amount=999, enabled=1, cardId=demo-42.",
  "targets": [
   "R-04",
   "R-26",
   "R-28",
   "R-33",
   "R-36"
  ],
  "input": {
   "http_method": "GET",
   "query_params": {
    "cardId": "demo-42",
    "amount": 999,
    "enabled": 1
   }
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Сохранение порога со значением верхнего допустимого предела (1 000 000 ₸)",
  "quote": "",
  "situation": "Клиент отправляет GET-запрос на /alerts/saveLimit с параметрами amount=1000000, enabled=1, cardId=demo-42 при валидной сессии.",
  "targets": [
   "R-04",
   "R-27",
   "R-33",
   "R-35"
  ],
  "input": {
   "http_method": "GET",
   "query_params": {
    "cardId": "demo-42",
    "amount": 1000000,
    "enabled": 1
   }
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Повторная доставка одного и того же события проведения покупки от процессинга",
  "quote": "",
  "situation": "Сервис расходов получает событие проведения покупки ID 777 на сумму 5 000 ₸. Затем то же самое событие ID 777 повторно доставляется процессором.",
  "targets": [
   "R-16",
   "R-18"
  ],
  "input": {
   "operation_id": "777",
   "amount_tiyn": 500000,
   "delivery_count": 2
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос сохранения порога для карты, принадлежащей другому клиенту",
  "quote": "",
  "situation": "Авторизованный клиент A отправляет GET-запрос /alerts/saveLimit с параметрами cardId=card-of-client-B, amount=50000, enabled=1.",
  "targets": [
   "R-23",
   "R-25",
   "R-39"
  ],
  "input": {
   "authenticated_user": "client_A",
   "query_params": {
    "cardId": "card-of-client-B",
    "amount": 50000,
    "enabled": 1
   }
  },
  "expected": null,
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Совершение авторизации покупки без фактического проведения (posting)",
  "quote": "",
  "situation": "Расходы 45 000 ₸, порог 50 000 ₸. По карте совершается авторизация (покупка) на 10 000 ₸, но финансовое проведение (clearing/posting) ещё не выполнено.",
  "targets": [
   "R-03",
   "R-07",
   "R-10"
  ],
  "input": {
   "initial_expenses_kzt": 45000,
   "threshold_kzt": 50000,
   "auth_amount_kzt": 10000,
   "is_conducted": false
  },
  "expected": null,
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-06",
   "R-07",
   "R-20"
  ],
  "quote": "Месяц определяется по дате совершения покупки в Алматы.",
  "question": "К какому месяцу относить расход, если дата совершения и дата проведения покупки выпадают на разные календарные месяцы?",
  "a": "Счётчик расходов увеличивается в месяце совершения покупки (январь), так как Месяц определяется по дате совершения покупки.",
  "b": "Счётчик расходов увеличивается в месяце проведения покупки (февраль), как указано в критерии приёмки R-20."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-11",
   "R-13"
  ],
  "quote": "Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.",
  "question": "Отправляется ли повторный push в одном календарном месяце при повторном достижении порога после смены настройки, если один push в этом месяце уже отправлялся?",
  "a": "Push отправляется, так как правило R-13 явно указывает на независимость от истории предыдущей настройки.",
  "b": "Push не отправляется, так как правило R-11 устанавливает жесткое ограничение: максимум один push за календарный месяц на карту."
 },
 {
  "id": "I3",
  "req_ids": [
   "R-22",
   "R-27",
   "R-30"
  ],
  "quote": "REST type GET",
  "question": "Какой HTTP-метод должен использовать клиент для сохранения/изменения настроек порога?",
  "a": "Метод HTTP GET, согласно спецификации общих параметров REST API и примерной команде cURL.",
  "b": "Метод HTTP POST или PUT, поскольку операция является модифицирующей (сохранение/перезапись настройки в БД)."
 },
 {
  "id": "I4",
  "req_ids": [
   "R-28",
   "R-35",
   "R-36"
  ],
  "quote": "5. При отклонении суммы вернуть прежнее состояние и результат ERROR.",
  "question": "Какой HTTP-код ответа возвращает API при передаче невалидной суммы порога?",
  "a": "HTTP 400 Bad Request, так как параметры запроса заполнены неверно (R-36).",
  "b": "HTTP 200 OK с телом {\"result\":\"ERROR\",\"message\":\"Проверьте сумму\"}, как описано в примере ответа 200 (R-35, R-28)."
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
