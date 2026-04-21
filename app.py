from flask import Flask, render_template, request
import math

app = Flask(__name__)

DEFAULTS = {
    "sell_price_per_block": 750.0,
    "blaze_rod_cost": 150.0,
    "seconds_per_smoker_item": 5.0,
    "items_per_blaze_rod": 12.0,
    "seconds_per_growth_tick": 4.0,
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

    total_seconds = hours * 3600.0

    # Farm-side production estimate based on average kelp growth interval per plant.
    farm_raw_kelp = (total_seconds / seconds_per_growth_tick) * kelp_plants

    # Smoker-side maximum throughput.
    smoker_capacity_raw_kelp = (total_seconds / seconds_per_smoker_item) * smokers

    # True processed output is limited by whichever side is smaller.
    processed_raw_kelp = min(farm_raw_kelp, smoker_capacity_raw_kelp)
    unused_farm_output = max(farm_raw_kelp - smoker_capacity_raw_kelp, 0.0)

    dried_kelp_items = processed_raw_kelp
    dried_kelp_blocks = dried_kelp_items / 9.0
    dried_kelp_block_stacks = dried_kelp_blocks / 64.0

    blaze_rods_total = processed_raw_kelp / items_per_blaze_rod
    blaze_rod_stacks_total = blaze_rods_total / 64.0
    blaze_rods_per_smoker = blaze_rods_total / smokers if smokers > 0 else 0.0
    blaze_rod_stacks_per_smoker = blaze_rods_per_smoker / 64.0

    gross_revenue = dried_kelp_blocks * sell_price_per_block
    blaze_rod_total_cost = blaze_rods_total * blaze_rod_cost
    net_profit = gross_revenue - blaze_rod_total_cost

    bottleneck = "farm growth" if farm_raw_kelp < smoker_capacity_raw_kelp else "smokers"
    smoker_utilization = (processed_raw_kelp / smoker_capacity_raw_kelp * 100.0) if smoker_capacity_raw_kelp > 0 else 0.0
    farm_utilization = (processed_raw_kelp / farm_raw_kelp * 100.0) if farm_raw_kelp > 0 else 0.0

    return {
        "inputs": {
            "kelp_plants": kelp_plants,
            "smokers": smokers,
            "hours": hours,
            "sell_price_per_block": sell_price_per_block,
            "blaze_rod_cost": blaze_rod_cost,
            "seconds_per_smoker_item": seconds_per_smoker_item,
            "items_per_blaze_rod": items_per_blaze_rod,
            "seconds_per_growth_tick": seconds_per_growth_tick,
        },
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
        "fmt_money": fmt_money,
        "fmt_num": fmt_num,
    }

@app.route("/", methods=["GET", "POST"])
def index():
    form = DEFAULTS.copy()
    form.update({
        "kelp_plants": 45,
        "smokers": 2,
        "hours": 24,
    })

    results = None
    error = None

    if request.method == "POST":
        try:
            form = {
                "kelp_plants": request.form.get("kelp_plants", 45),
                "smokers": request.form.get("smokers", 2),
                "hours": request.form.get("hours", 24),
                "sell_price_per_block": request.form.get("sell_price_per_block", DEFAULTS["sell_price_per_block"]),
                "blaze_rod_cost": request.form.get("blaze_rod_cost", DEFAULTS["blaze_rod_cost"]),
                "seconds_per_smoker_item": request.form.get("seconds_per_smoker_item", DEFAULTS["seconds_per_smoker_item"]),
                "items_per_blaze_rod": request.form.get("items_per_blaze_rod", DEFAULTS["items_per_blaze_rod"]),
                "seconds_per_growth_tick": request.form.get("seconds_per_growth_tick", DEFAULTS["seconds_per_growth_tick"]),
            }

            numeric_values = {k: float(v) for k, v in form.items()}
            if numeric_values["kelp_plants"] <= 0:
                raise ValueError("Kelp plants must be greater than 0.")
            if numeric_values["smokers"] <= 0:
                raise ValueError("Smokers must be greater than 0.")
            if numeric_values["hours"] <= 0:
                raise ValueError("Run time must be greater than 0.")
            if numeric_values["sell_price_per_block"] < 0 or numeric_values["blaze_rod_cost"] < 0:
                raise ValueError("Prices cannot be negative.")
            if numeric_values["seconds_per_smoker_item"] <= 0 or numeric_values["items_per_blaze_rod"] <= 0 or numeric_values["seconds_per_growth_tick"] <= 0:
                raise ValueError("Timing and fuel values must be greater than 0.")

            results = calc(numeric_values)
            form = numeric_values
        except Exception as exc:
            error = str(exc)

    return render_template("index.html", form=form, results=results, error=error)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
