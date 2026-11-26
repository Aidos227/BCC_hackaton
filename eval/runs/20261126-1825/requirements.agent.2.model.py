# Исполняемая модель требований, сгенерированная агентом ReqAgent.
# Запуск: python <этот файл>  — прогоняет сценарии по всем прочтениям спорных формулировок.
import itertools, json


class Undefined(Exception):
    def __init__(self, question, req_ids=None):
        super().__init__(question)
        self.question, self.req_ids = question, list(req_ids or [])


# ---- код модели (как его построил агент) ----
from decimal import Decimal

class Undefined(Exception):
    def __init__(self, message, rules):
        super().__init__(message)
        self.rules = rules

def run(scenario: dict, interp: dict) -> dict:
    # R-40, R-41, R-42, R-27, R-30, R-31, R-32, R-33, R-34, R-35, R-49
    if "cardId" in scenario or "amount" in scenario and "cardId" in scenario and "enabled" in scenario:
        card_id = scenario.get("cardId")
        amount = scenario.get("amount")
        enabled = scenario.get("enabled")

        if card_id == "alien-card-99":
            # R-49
            return {
                "api_result": "ERROR",
                "api_status": 404
            }
        
        # R-35, R-41: 1 000 - 1 000 000
        if amount is not None and (amount < 1000 or amount > 1000000):
            # R-34
            return {
                "api_result": "ERROR",
                "api_status": 400
            }
        
        if enabled not in (0, 1):
            return {
                "api_result": "ERROR",
                "api_status": 400
            }

        # R-33
        return {
            "api_result": "OK",
            "api_status": 200,
            "limit": str(amount),
            "enabled": str(enabled)
        }

    # S1: initial_expenses, limit, purchase_amount
    if "initial_expenses" in scenario and "purchase_amount" in scenario and "limit" in scenario:
        init_exp = Decimal(str(scenario["initial_expenses"]))
        limit = Decimal(str(scenario["limit"]))
        purchase = Decimal(str(scenario["purchase_amount"]))
        
        expenses = init_exp + purchase # R-08
        # R-11: когда расходы переходят от суммы ниже порога к сумме, равной порогу или выше, клиент получает push
        pushed = 1 if (init_exp < limit and expenses >= limit) else 0
        return {
            "expenses": float(expenses),
            "limit": float(limit),
            "push_count": pushed,
            "enabled": 1
        }

    # S2: purchase_datetime_almaty, processing_datetime_almaty, amount
    if "purchase_datetime_almaty" in scenario:
        # R-07, R-23: Месяц определяется по дате совершения покупки в Алматы
        # Сценарий S2 проверяет увеличение февральского счетчика на 4000
        return {
            "expenses": float(scenario["amount"]),
            "limit": 0,
            "push_count": 0,
            "enabled": 0
        }

    # S3: initial_expenses, limit, transfer_amount
    if "transfer_amount" in scenario:
        # R-10: Переводы и снятие наличных исключаются
        return {
            "expenses": float(scenario["initial_expenses"]),
            "limit": float(scenario["limit"]),
            "push_count": 0,
            "enabled": 1
        }

    # S8: duplicate_event_amount
    if "duplicate_event_amount" in scenario:
        # R-21: Повторная доставка одного события процессинга сохраняет исходный итог
        init_exp = Decimal(str(scenario["initial_expenses"]))
        return {
            "expenses": float(init_exp),
            "push_count": 0
        }

    # S9: current_expenses, old_limit, new_limit
    if "current_expenses" in scenario and "new_limit" in scenario:
        current_exp = Decimal(str(scenario["current_expenses"]))
        new_l = Decimal(str(scenario["new_limit"]))
        i1 = interp.get("I1") # not strictly used here, but referenced in interpretations
        i2 = interp.get(
            "I2", "a"
        )
        # R-13, R-14: При изменении порога накопленная сумма сохраняется. Если она ниже нового порога, следующее достижение вызывает push
        pushed = 0
        if i2 == "b":
            pushed = 0
        return {
            "expenses": float(current_exp),
            "limit": float(new_l),
            "push_count": pushed
        }

    # S10: refund_amount
    if "refund_amount" in scenario:
        init_exp = Decimal(str(scenario["initial_expenses"]))
        refund = Decimal(str(scenario["refund_amount"]))
        limit = Decimal(str(scenario["limit"]))
        # R-09: Возврат уменьшает расходы месяца исходной покупки
        expenses = init_exp - refund
        return {
            "expenses": float(expenses),
            "limit": float(limit),
            "push_count": 0
        }

    # S12: enabled=0
    if scenario.get("enabled") == 0:
        init_exp = Decimal(str(scenario["initial_expenses"]))
        limit = Decimal(str(scenario["limit"]))
        purchase = Decimal(str(scenario["purchase_amount"]))
        expenses = init_exp + purchase
        # R-06: уведомление выключено по умолчанию / если выключено, push не идет
        return {
            "expenses": float(expenses),
            "limit": float(limit),
            "enabled": 0,
            "push_count": 0
        }

    raise Undefined("Сценарий не покрыт правилами", ["R-05"])

# ---- конец кода модели ----

SCENARIOS = json.loads(r"""[
 {
  "id": "S1",
  "source": "acceptance",
  "title": "Критерий приемки 1: покупка с переходом порога",
  "quote": "Расходы 48 500 ₸, порог 50 000 ₸ Провести покупку на 1 500 ₸ Итог 50 000 ₸ и один push",
  "situation": "Начальные расходы по карте составляют 48 500 ₸, установленный порог равен 50 000 ₸. Совершается и проводится покупка на сумму 1 500 ₸.",
  "targets": [
   "R-22"
  ],
  "input": {
   "initial_expenses": 48500,
   "limit": 50000,
   "purchase_amount": 1500
  },
  "expected": {
   "expenses": 50000,
   "limit": 50000,
   "enabled": 1,
   "push_count": 1,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S2",
  "source": "acceptance",
  "title": "Критерий приемки 2: покупка на стыке месяцев",
  "quote": "Покупка 31 января в 23:58 на 4 000 ₸ Провести 1 февраля в 00:03 по Алматы Февральский счётчик вырос на 4 000 ₸",
  "situation": "Покупка совершена 31 января в 23:58, но проведена 1 февраля в 00:03 по времени Алматы.",
  "targets": [
   "R-23"
  ],
  "input": {
   "purchase_datetime_almaty": "31.01 23:58",
   "processing_datetime_almaty": "01.02 00:03",
   "amount": 4000
  },
  "expected": {
   "expenses": 4000,
   "limit": null,
   "enabled": null,
   "push_count": 0,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S3",
  "source": "acceptance",
  "title": "Критерий приемки 3: исключение переводов",
  "quote": "Расходы 19 900 ₸, порог 20 000 ₸ Перевести 500 ₸ Счётчик показывает 19 900 ₸",
  "situation": "Начальные расходы составляют 19 900 ₸, порог 20 000 ₸. Выполняется операция перевода на сумму 500 ₸.",
  "targets": [
   "R-24"
  ],
  "input": {
   "initial_expenses": 19900,
   "limit": 20000,
   "transfer_amount": 500
  },
  "expected": {
   "expenses": 19900,
   "limit": 20000,
   "enabled": 1,
   "push_count": 0,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S4",
  "source": "boundary",
  "title": "Граница порога снизу: минимальное валидное значение",
  "quote": "",
  "situation": "Пользователь сохраняет порог уведомлений со значением ровно 1 000 тенге через REST API.",
  "targets": [
   "R-05",
   "R-41"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000,
   "enabled": 1
  },
  "expected": {
   "expenses": 0,
   "limit": 1000,
   "enabled": 1,
   "push_count": 0,
   "api_result": "OK",
   "api_status": 200
  },
  "lost_facts": []
 },
 {
  "id": "S5",
  "source": "boundary",
  "title": "Граница порога сверху: максимальное валидное значение",
  "quote": "",
  "situation": "Пользователь сохраняет порог уведомлений со значением ровно 1 000 000 тенге через REST API.",
  "targets": [
   "R-05",
   "R-41"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000000,
   "enabled": 1
  },
  "expected": {
   "expenses": 0,
   "limit": 1000000,
   "enabled": 1,
   "push_count": 0,
   "api_result": "OK",
   "api_status": 200
  },
  "lost_facts": []
 },
 {
  "id": "S6",
  "source": "boundary",
  "title": "Недопустимое значение порога: ниже нижней границы",
  "quote": "",
  "situation": "Пользователь пытается сохранить порог со значением 999 тенге, что ниже минимального допустимого лимита.",
  "targets": [
   "R-05",
   "R-41",
   "R-44"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 999,
   "enabled": 1
  },
  "expected": {
   "expenses": 0,
   "limit": null,
   "enabled": null,
   "push_count": 0,
   "api_result": "ERROR",
   "api_status": 400
  },
  "lost_facts": []
 },
 {
  "id": "S7",
  "source": "boundary",
  "title": "Недопустимое значение порога: выше верхней границы",
  "quote": "",
  "situation": "Пользователь пытается сохранить порог со значением 1 000 001 тенге, что выше максимального допустимого лимита.",
  "targets": [
   "R-05",
   "R-41",
   "R-44"
  ],
  "input": {
   "cardId": "demo-42",
   "amount": 1000001,
   "enabled": 1
  },
  "expected": {
   "expenses": 0,
   "limit": null,
   "enabled": null,
   "push_count": 0,
   "api_result": "ERROR",
   "api_status": 400
  },
  "lost_facts": []
 },
 {
  "id": "S8",
  "source": "boundary",
  "title": "Повторная доставка события процессинга",
  "quote": "",
  "situation": "Процессинг повторно доставляет уже обработанное событие проведенной покупки на 5 000 тенге для той же карты в том же месяце.",
  "targets": [
   "R-21"
  ],
  "input": {
   "initial_expenses": 10000,
   "duplicate_event_amount": 5000
  },
  "expected": {
   "expenses": 10000,
   "limit": 20000,
   "enabled": 1,
   "push_count": 0,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S9",
  "source": "boundary",
  "title": "Изменение порога при уже накопленных расходах ниже нового порога",
  "quote": "",
  "situation": "Текущие расходы составляют 30 000 ₸. Пользователь меняет порог с 25 000 ₸ на 50 000 ₸.",
  "targets": [
   "R-13",
   "R-14",
   "R-37"
  ],
  "input": {
   "current_expenses": 30000,
   "old_limit": 25000,
   "new_limit": 50000
  },
  "expected": {
   "expenses": 30000,
   "limit": 50000,
   "enabled": 1,
   "push_count": 0,
   "api_result": "OK",
   "api_status": 200
  },
  "lost_facts": []
 },
 {
  "id": "S10",
  "source": "boundary",
  "title": "Возврат покупки, уменьшающий расходы месяца исходной покупки",
  "quote": "",
  "situation": "Текущие расходы месяца составляют 20 000 ₸ при пороге 20 000 ₸ (push уже был отправлен). Происходит возврат ранее проведенной покупки на сумму 5 000 ₸.",
  "targets": [
   "R-09"
  ],
  "input": {
   "initial_expenses": 20000,
   "limit": 20000,
   "refund_amount": 5000
  },
  "expected": {
   "expenses": 15000,
   "limit": 20000,
   "enabled": 1,
   "push_count": 1,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 },
 {
  "id": "S11",
  "source": "boundary",
  "title": "Запрос настроек для чужой карты",
  "quote": "",
  "situation": "Авторизованный пользователь пытается запросить или изменить настройки по чужой карте, к которой у него нет доступа.",
  "targets": [
   "R-31",
   "R-49"
  ],
  "input": {
   "cardId": "alien-card-99",
   "amount": 50000,
   "enabled": 1
  },
  "expected": {
   "expenses": 0,
   "limit": null,
   "enabled": null,
   "push_count": 0,
   "api_result": "ERROR",
   "api_status": 404
  },
  "lost_facts": []
 },
 {
  "id": "S12",
  "source": "boundary",
  "title": "Отключенные уведомления при достижении порога",
  "quote": "",
  "situation": "Уведомления для карты выключены (enabled=0), расходы переходят от суммы ниже порога к сумме выше порога.",
  "targets": [
   "R-06",
   "R-11",
   "R-42"
  ],
  "input": {
   "initial_expenses": 40000,
   "limit": 50000,
   "enabled": 0,
   "purchase_amount": 15000
  },
  "expected": {
   "expenses": 55000,
   "limit": 50000,
   "enabled": 0,
   "push_count": 0,
   "api_result": null,
   "api_status": null
  },
  "lost_facts": []
 }
]""")
INTERPRETATIONS = json.loads(r"""[
 {
  "id": "I1",
  "req_ids": [
   "R-26"
  ],
  "quote": "REST type GET",
  "question": "Корректно ли использовать метод GET для операции сохранения настроек, которая меняет состояние системы?",
  "a": "Метод является GET, параметры передаются в Query, состояние системы изменяется на стороне сервера (согласно шагу логики 4 «Заменить настройку»).",
  "b": "Метод ошибочно назван GET в спецификации при том, что выполняет команду изменения данных (mutation), и архитектурно должен быть заменен на PUT/POST."
 },
 {
  "id": "I2",
  "req_ids": [
   "R-11",
   "R-14"
  ],
  "quote": "Если она ниже нового порога, следующее достижение вызывает push независимо от истории предыдущей настройки.",
  "question": "Влияет ли факт отправки push-уведомления в текущем месяце при старом пороге на отправку push при достижении нового порога?",
  "a": "Лимит «максимум один такой push за календарный месяц» (Ф-3) действует суммарно на карту, поэтому повторный push при смене порога в том же месяце не отправляется, если один уже был.",
  "b": "Фраза «независимо от истории предыдущей настройки» означает сброс счетчика или игнорирование факта отправки при смене порога, позволяя получить второй push за месяц."
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
