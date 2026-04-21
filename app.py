from flask import Flask, render_template, request
import os

app = Flask(__name__)

DEFAULTS = {
    "kelp_plants": 45,
    "smokers": 2,
    "hours": 24,
    "sell_price_per_block": 750.0,
    "blaze_rod_cost": 150.0,
    "seconds_per_smoker_item": 5.0,
    "items_per_blaze_rod": 12.0,
    "seconds_per_growth_tick": 4.0,
}

def calc(data):
    kelp_plants = float(data["kelp_plants"])
    smokers = float(data["smokers"])
    hours = float(data["hours"])
    sell_price_per_block = float(data["sell_price_per_block"])
    blaze_rod_cost = float(data["blaze_rod_cost"])
    seconds_per_smoker_item = float(data["seconds_per_smoker_item"])
    items_per_blaze_rod = float(data["items_per_blaze_rod"])
    seconds_per_growth_tick = float(data["seconds_per_growth_tick"])

    total_seconds = hours * 3600.0

    farm_raw_kelp = (total_seconds / seconds_per_growth_tick) * kelp_plants
    smoker_capacity_raw_kelp = (total_seconds / seconds_per_smoker_item) * smokers
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
    smoker_utilization = (processed_raw_kelp / smoker_capacity_raw_kelp * 100.0) if smoker_capacity_raw_kelp > 0 else 0.0
    farm_utilization = (processed_raw_kelp / farm_raw_kelp * 100.0) if farm_raw_kelp > 0 else 0.0

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
    }

def fmt_money(value):
    return "${:,.2f}".format(value)

def fmt_num(value):
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"

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
                "sell_price_per_block": float(request.form.get("sell_price_per_block", DEFAULTS["sell_price_per_block"])),
                "blaze_rod_cost": float(request.form.get("blaze_rod_cost", DEFAULTS["blaze_rod_cost"])),
                "seconds_per_smoker_item": float(request.form.get("seconds_per_smoker_item", DEFAULTS["seconds_per_smoker_item"])),
                "items_per_blaze_rod": float(request.form.get("items_per_blaze_rod", DEFAULTS["items_per_blaze_rod"])),
                "seconds_per_growth_tick": float(request.form.get("seconds_per_growth_tick", DEFAULTS["seconds_per_growth_tick"])),
            }

            if form["kelp_plants"] <= 0:
                raise ValueError("Kelp plants must be greater than 0.")
            if form["smokers"] <= 0:
                raise ValueError("Smokers must be greater than 0.")
            if form["hours"] <= 0:
                raise ValueError("Run time must be greater than 0.")

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
    app.run(host="0.0.0.0", port=port)
