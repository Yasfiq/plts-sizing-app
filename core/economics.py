from typing import Optional

def calc_financial_metrics(
    kwp: float,
    battery_kwh: float,
    annual_energy_kwh: float,
    tarif_pln: float = 1444.70,
    mod_cost_wp: float = 3500.0,
    inv_cost_w: float = 1200.0,
    battery_cost_kwh: float = 3500000.0,
    bos_cost: Optional[float] = None,
    annual_opex: Optional[float] = None,
    bos_cost_pct: float = 0.15,
    opex_pct: float = 0.015,
    discount_rate: float = 0.08,
    degradation_rate: float = 0.007,
    years: int = 25,
) -> dict:
    # ponytail: basic linear cashflow; add loan debt service and tax depreciation when project finance required
    pv_cost = kwp * 1000.0 * mod_cost_wp
    inv_cost = kwp * 1000.0 * inv_cost_w
    bat_cost = battery_kwh * battery_cost_kwh
    base_component = pv_cost + inv_cost + bat_cost
    
    if bos_cost is None:
        bos_cost = base_component * bos_cost_pct
    capex = base_component + bos_cost

    if annual_opex is None:
        annual_opex = capex * opex_pct

    npv = -capex
    cum_cash = -capex
    payback_years = None

    pv_discounted_costs = capex
    pv_discounted_energy = 0.0

    cashflows = [{
        "year": 0,
        "energy_kwh": 0.0,
        "savings": 0.0,
        "opex": 0.0,
        "net_cash": -capex,
        "cum_cash": -capex,
        "discounted_net_cash": -capex,
    }]

    for t in range(1, years + 1):
        eff = 1.0 - (t - 1) * degradation_rate
        gen_t = annual_energy_kwh * eff
        saving_t = gen_t * tarif_pln
        net_cash_t = saving_t - annual_opex

        cum_cash_prev = cum_cash
        cum_cash += net_cash_t
        if cum_cash >= 0 and payback_years is None:
            payback_years = (t - 1) + (-cum_cash_prev / net_cash_t)

        discount_factor = (1.0 + discount_rate) ** t
        disc_net = net_cash_t / discount_factor
        npv += disc_net

        pv_discounted_costs += annual_opex / discount_factor
        pv_discounted_energy += gen_t / discount_factor

        cashflows.append({
            "year": t,
            "energy_kwh": gen_t,
            "savings": saving_t,
            "opex": annual_opex,
            "net_cash": net_cash_t,
            "cum_cash": cum_cash,
            "discounted_net_cash": disc_net,
        })

    lcoe = pv_discounted_costs / pv_discounted_energy if pv_discounted_energy > 0 else 0.0

    return {
        "capex": capex,
        "annual_opex": annual_opex,
        "first_year_saving": annual_energy_kwh * tarif_pln,
        "payback_years": payback_years if payback_years is not None else float("inf"),
        "npv": npv,
        "lcoe_per_kwh": lcoe,
        "cashflows": cashflows,
    }
