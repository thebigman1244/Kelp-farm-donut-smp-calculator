from flask import Flask, render_template, request
import os

app = Flask(__name__)

def calculate(data):
    kelp_plants = float(data["kelp_plants"])
    smokers = float(data["smokers"])
    hours = float(data["hours"])
    sell_price = float(data["sell_price"])
    rod_cost = float(data["rod_cost"])

    seconds = hours * 3600

    # Kelp growth (approx 1 growth every 4 seconds per plant)
    kelp_generated = (seconds / 4) * kelp_plants

    # Smoker capacity (1 item every 5 seconds)
    smoker_capacity = (seconds / 5) * smokers

    # Real output = bottleneck
    processed_kelp = min(kelp_generated, smoker_capacity)

    dried_blocks = processed_kelp / 9
    block_stacks = dried_blocks / 64

    rods_needed = processed_kelp / 12
    rod_stacks = rods_needed / 64

    rods_per_smoker = rods_needed / smokers if smokers > 0 else 0
    stacks_per_smoker = rods_per_smoker / 64

    revenue = dried_blocks * sell_price
    rod_total_cost = rods_needed * rod_cost
    profit = revenue - rod_total_cost

    bottleneck = "Farm Growth" if kelp_generated < smoker_capacity else "Smokers"

    return {
        "kelp_generated": kelp_generated,
        "processed_kelp": processed_kelp,
        "dried_blocks": dried_blocks,
        "block_stacks": block_stacks,
        "rods_needed": rods_needed,
        "rod_stacks": rod_stacks,
        "rods_per_smoker": rods_per_smoker,
        "stacks_per_smoker": stacks_per_smoker,
        "revenue": revenue,
        "rod_total_cost": rod_total_cost,
        "profit": profit,
        "bottleneck": bottleneck
    }

@app.route("/", methods=["GET", "POST"])
def index():
    results = None

    if request.method == "POST":
        data = request.form
        results = calculate(data)

    return render_template("index.html", results=results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
