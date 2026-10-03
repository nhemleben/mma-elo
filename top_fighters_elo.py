import argparse
import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


DATA_DIR = Path(__file__).resolve().parent
DATE_FORMATS = ("%B %d, %Y", "%B %d %Y", "%d %B, %Y", "%d %B %Y")


def parse_date(value):
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported fight date: {value!r}")


def load_results():
    results = []
    required_fields = {"Fighter", "Result", "Opponent", "Date", "Fight Number"}

    for filename in ("results.csv", "results_extra.csv"):
        path = DATA_DIR / filename
        with path.open(newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file, delimiter=";")
            missing_fields = required_fields - set(reader.fieldnames or [])
            if missing_fields:
                raise ValueError(f"{filename} is missing columns: {', '.join(sorted(missing_fields))}")

            for row in reader:
                results.append({
                    "fighter": row["Fighter"].strip(),
                    "result": row["Result"].strip(),
                    "opponent": row["Opponent"].strip(),
                    "date": parse_date(row["Date"].strip()),
                    "fight_number": int(row["Fight Number"]),
                    "source_order": len(results),
                })

    results.sort(key=lambda fight: (fight["date"], fight["fight_number"], fight["source_order"]))
    return results


def expected_score(rating, opponent_rating):
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))


def calculate_histories(results):
    names = dict.fromkeys(
        [fight["fighter"] for fight in results]
        + [fight["opponent"] for fight in results]
    )
    ratings = dict.fromkeys(names, 1000)
    histories = defaultdict(list)

    for fight in results:
        fighter = fight["fighter"]
        opponent = fight["opponent"]
        for name in (fighter, opponent):
            if not histories[name]:
                histories[name].append({
                    "date": fight["date"] - timedelta(days=1),
                    "fight_number": 0,
                    "opponent": "",
                    "result": "Starting rating",
                    "elo": ratings[name],
                })

        if fight["result"] in ("def.", "def"):
            fighter_result, opponent_result = 1, 0
        elif fight["result"] in ("vs.", "vs"):
            fighter_result, opponent_result = 0.5, 0.5
        else:
            continue

        fighter_expected = expected_score(ratings[fighter], ratings[opponent])
        opponent_expected = 1 - fighter_expected
        ratings[fighter] = round(ratings[fighter] + 32 * (fighter_result - fighter_expected))
        ratings[opponent] = round(ratings[opponent] + 32 * (opponent_result - opponent_expected))

        histories[fighter].append({
            "date": fight["date"],
            "fight_number": fight["fight_number"],
            "opponent": opponent,
            "result": fight["result"],
            "elo": ratings[fighter],
        })
        histories[opponent].append({
            "date": fight["date"],
            "fight_number": fight["fight_number"],
            "opponent": fighter,
            "result": "loss" if fighter_result == 1 else fight["result"],
            "elo": ratings[opponent],
        })

    ranking = sorted(ratings.items(), key=lambda item: -item[1])
    return ranking, histories


def save_timeseries(filename, ranked_fighters, histories):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=("Rank", "Fighter", "Date", "Fight Number", "Opponent", "Result", "Elo"),
        )
        writer.writeheader()
        for rank, (fighter, _) in enumerate(ranked_fighters, start=1):
            for entry in histories[fighter]:
                writer.writerow({
                    "Rank": rank,
                    "Fighter": fighter,
                    "Date": entry["date"].isoformat(),
                    "Fight Number": entry["fight_number"],
                    "Opponent": entry["opponent"],
                    "Result": entry["result"],
                    "Elo": entry["elo"],
                })


def save_plot(filename, ranked_fighters, histories):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(15, 8))
    colors = plt.get_cmap("tab20")

    for rank, (fighter, rating) in enumerate(ranked_fighters, start=1):
        entries = histories[fighter]
        axis.step(
            [entry["date"] for entry in entries],
            [entry["elo"] for entry in entries],
            where="post",
            linewidth=1.7,
            color=colors((rank - 1) % 20),
            label=f"{fighter} ({rating})",
        )

    axis.axhline(1000, color="gray", linestyle="--", linewidth=1, label="Starting Elo")
    axis.set_title(f"Career Elo for the top {len(ranked_fighters)} fighters")
    axis.set_xlabel("Fight date")
    axis.set_ylabel("Elo rating")
    axis.xaxis.set_major_locator(mdates.AutoDateLocator())
    axis.xaxis.set_major_formatter(mdates.ConciseDateFormatter(axis.xaxis.get_major_locator()))
    axis.grid(axis="y", alpha=0.25)
    axis.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
    figure.subplots_adjust(right=0.73)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(
        description="Save the top fighters' career Elo histories and plot them together."
    )
    parser.add_argument("-n", "--top", type=int, default=10, help="number of current top fighters (default: 10)")
    parser.add_argument("--csv", default=None, help="timeseries CSV output path")
    parser.add_argument("--plot", default=None, help="plot image output path")
    args = parser.parse_args()
    if args.top < 1:
        parser.error("--top must be at least 1")

    results = load_results()
    ranking, histories = calculate_histories(results)
    ranked_fighters = ranking[:args.top]
    csv_path = args.csv or f"top_{len(ranked_fighters)}_elo_timeseries.csv"
    plot_path = args.plot or f"top_{len(ranked_fighters)}_elo.png"

    save_timeseries(csv_path, ranked_fighters, histories)
    save_plot(plot_path, ranked_fighters, histories)
    print(f"Saved {len(ranked_fighters)} fighters' histories to {csv_path}")
    print(f"Saved combined Elo plot to {plot_path}")
    for rank, (fighter, rating) in enumerate(ranked_fighters, start=1):
        print(f"{rank:>2}. {fighter}: {rating}")


if __name__ == "__main__":
    main()