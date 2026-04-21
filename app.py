from flask import Flask, render_template, request
import os
import math

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-later")


DEFAULTS = {
    "kelp_plants": 45,
    "smokers": 2,
    "hours": 24,
    "sell_price_per_block": 750.0,
    "blaze_rod_cost": 150.0,
    "seconds_per_smoker_item": 5.0,
    "items_per_blaze_rod": 12.0,
    "seconds_per_growth_tick": 4.0,
    "target_money": 1_000_000_000.0,
    "target_days": 60.0,
}


def fmt_money(value: float) -> str:
    return "${:,.2f}".format(value)


def fmt_num(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"


def calc(data: dict) -> dict:
    kelp_plants = float(data["kelp_plants"])
    smokers = float(data["smokers"])
    hours = float(data["hours"])
    sell_price_per_block = float(data["sell_price_per_block"])
    blaze_rod_cost = float(data["blaze_rod_cost"])
    seconds_per_smoker_item = float(data["seconds_per_smoker_item"])
    items_per_blaze_rod = float(data["items_per_blaze_rod"])
    seconds_per_growth_tick = float(data["seconds_per_growth_tick"])
    target_money = float(data["target_money"])
    target_days = float(data["target_days"])

    total_seconds = hours * 3600.0

    # Farm-side production estimate
    farm_raw_kelp = (total_seconds / seconds_per_growth_tick) * kelp_plants

    # Smoker-side max capacity
    smoker_capacity_raw_kelp = (total_seconds / seconds_per_smoker_item) * smokers

    # True processed total
    processed_raw_kelp = min(farm_raw_kelp, smoker_capacity_raw_kelp)
    unused_farm_output = max(farm_raw_kelp - smoker_capacity_raw_kelp, 0.0)

    dried_kelp_blocks = processed_raw_kelp / 9.0
    dried_kelp_block_stacks = dried_kelp_blocks / 64.0

    blaze_rods_total = processed_raw_kelp / items_per_blaze_rod
    blaze_rod_stacks_total = blaze_rods_total / 64.0
    blaze_rods_per_smoker = blaze_rods_total / smokers if smokers > 0 else 0.0
    blaze_rod_stacks_per_smoker = blaze_rods_per_smoker / 64.0

    gross_revenue = dried_kelp_blocks * sell_price_per_block
    blaze_rod_total_cost = blaze_rods_total * blaze_rod_cost
    net_profit = gross_revenue - blaze_rod_total_cost

    bottleneck = "farm growth" if farm_raw_kelp < smoker_capacity_raw_kelp else "smokers"

    smoker_utilization = (
        (processed_raw_kelp / smoker_capacity_raw_kelp) * 100.0
        if smoker_capacity_raw_kelp > 0
        else 0.0
    )
    farm_utilization = (
        (processed_raw_kelp / farm_raw_kelp) * 100.0
        if farm_raw_kelp > 0
        else 0.0
    )

    # Profit rates
    profit_per_hour = net_profit / hours if hours > 0 else 0.0
    profit_per_day = profit_per_hour * 24.0

    # Time to 1B
    one_billion = 1_000_000_000.0
    if profit_per_day > 0:
        days_to_1b = one_billion / profit_per_day
        hours_to_1b = days_to_1b * 24.0
    else:
        days_to_1b = None
        hours_to_1b = None

    # Target planner
    target_daily_profit = target_money / target_days if target_days > 0 else 0.0

    # Net profit per raw kelp item processed
    gross_per_raw_kelp = sell_price_per_block / 9.0
    fuel_per_raw_kelp = blaze_rod_cost / items_per_blaze_rod
    net_per_raw_kelp = gross_per_raw_kelp - fuel_per_raw_kelp

    if net_per_raw_kelp > 0 and target_daily_profit > 0:
        required_processed_raw_kelp_per_day = target_daily_profit / net_per_raw_kelp

        required_plants = math.ceil(
            required_processed_raw_kelp_per_day * seconds_per_growth_tick / 86400.0
        )
        required_smokers = math.ceil(
            required_processed_raw_kelp_per_day * seconds_per_smoker_item / 86400.0
        )

        scale_multiplier = (
            target_daily_profit / profit_per_day if profit_per_day > 0 else None
        )
    else:
        required_processed_raw_kelp_per_day = None
        required_plants = None
        required_smokers = None
        scale_multiplier = None

    return {
        "farm_raw_kelp": farm_raw_kelp,
        "smoker_capacity_raw_kelp": smoker_capacity_raw_kelp,
        "processed_raw_kelp": processed_raw_kelp,
        "unused_farm_output": unused_farm_output,
        "dried_kelp_blocks": dried_kelp_blocks,
        "dried_kelp_block_stacks": dried_kelp_block_stacks,
        "blaze_rods_total": blaze_rods_total,
        "blaze_rod_stacks_total": blaze_rod_stacks_total,
        "blaze_rods_per_smoker": blaze_rods_per_smoker,
        "blaze_rod_stacks_per_smoker": blaze_rod_stacks_per_smoker,
        "gross_revenue": gross_revenue,
        "blaze_rod_total_cost": blaze_rod_total_cost,
        "net_profit": net_profit,
        "bottleneck": bottleneck,
        "smoker_utilization": smoker_utilization,
        "farm_utilization": farm_utilization,
        "profit_per_hour": profit_per_hour,
        "profit_per_day": profit_per_day,
        "days_to_1b": days_to_1b,
        "hours_to_1b": hours_to_1b,
        "target_money": target_money,
        "target_days": target_days,
        "target_daily_profit": target_daily_profit,
        "required_processed_raw_kelp_per_day": required_processed_raw_kelp_per_day,
        "required_plants": required_plants,
        "required_smokers": required_smokers,
        "scale_multiplier": scale_multiplier,
        "net_per_raw_kelp": net_per_raw_kelp,
    }


@app.route("/", methods=["GET", "POST"])
def index():
    form = DEFAULTS.copy()
    results = None
    error = None

    if request.method == "POST":
        try:
            form = {
                "kelp_plants": float(request.form.get("kelp_plants", DEFAULTS["kelp_plants"])),
                "smokers": float(request.form.get("smokers", DEFAULTS["smokers"])),
                "hours": float(request.form.get("hours", DEFAULTS["hours"])),
                "sell_price_per_block": float(
                    request.form.get("sell_price_per_block", DEFAULTS["sell_price_per_block"])
                ),
                "blaze_rod_cost": float(
                    request.form.get("blaze_rod_cost", DEFAULTS["blaze_rod_cost"])
                ),
                "seconds_per_smoker_item": float(
                    request.form.get(
                        "seconds_per_smoker_item", DEFAULTS["seconds_per_smoker_item"]
                    )
                ),
                "items_per_blaze_rod": float(
                    request.form.get("items_per_blaze_rod", DEFAULTS["items_per_blaze_rod"])
                ),
                "seconds_per_growth_tick": float(
                    request.form.get(
                        "seconds_per_growth_tick", DEFAULTS["seconds_per_growth_tick"]
                    )
                ),
                "target_money": float(
                    request.form.get("target_money", DEFAULTS["target_money"])
                ),
                "target_days": float(
                    request.form.get("target_days", DEFAULTS["target_days"])
                ),
            }

            if form["kelp_plants"] <= 0:
                raise ValueError("Kelp plants must be greater than 0.")
            if form["smokers"] <= 0:
                raise ValueError("Smokers must be greater than 0.")
            if form["hours"] <= 0:
                raise ValueError("Run time must be greater than 0.")
            if form["target_money"] <= 0:
                raise ValueError("Target money must be greater than 0.")
            if form["target_days"] <= 0:
                raise ValueError("Target days must be greater than 0.")
            if form["sell_price_per_block"] < 0 or form["blaze_rod_cost"] < 0:
                raise ValueError("Prices cannot be negative.")
            if (
                form["seconds_per_smoker_item"] <= 0
                or form["items_per_blaze_rod"] <= 0
                or form["seconds_per_growth_tick"] <= 0
            ):
                raise ValueError("Timing and fuel values must be greater than 0.")

            results = calc(form)

        except Exception as exc:
            error = str(exc)

    return render_template(
        "index.html",
        form=form,
        results=results,
        error=error,
        fmt_money=fmt_money,
        fmt_num=fmt_num,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
