# CourtVision AI: A Guide for Everyone

This guide is written for people who do not write software. It explains what
CourtVision AI is, how to start it on your own computer, and how to use every part
of it. You do not need to understand any of the code.

If a step ever fails, jump to [If something goes wrong](#if-something-goes-wrong)
near the bottom.

---

## What is CourtVision AI?

CourtVision AI is a basketball analytics website that runs on your own computer. It
collects real NBA statistics from the league's public stats service, organizes them
into a fast database, and turns them into things you can actually explore: team
rankings, player careers, leaderboards, game predictions, and an assistant that
answers basketball questions in plain English.

Think of it as a private version of the analytics tools an NBA front office or a
sports network would use internally. Nothing is sent anywhere. The data sits on your
machine, and the website is only visible to you.

---

## What you need

1. **A computer** running macOS, Windows, or Linux.
2. **Docker Desktop**, a free program that runs the app in a self-contained bundle
   so you do not have to install anything else. Download it from
   [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop),
   install it, and open it once so it is running. You will see a small whale icon in
   your menu bar or system tray when it is ready.
3. **About 10 minutes** the first time. After that, starting the app takes seconds.

You will type a few commands into the Terminal app (on Mac, press Command and Space,
type "Terminal", press Enter). Every command below can be copied and pasted. You do
not need to understand them.

---

## Starting the app

First, point the Terminal at the project folder. Copy this line, paste it, press Enter:

```bash
cd "/Users/apple/Desktop/ /Knowledge Building/Projects/CourtVision AI"
```

Now pick one of the two options below.

### Option A: Try it right away (fake data, zero setup)

This starts the app with realistic but invented statistics. It is perfect for seeing
how everything works before dealing with real data.

```bash
COURTVISION_DEMO=1 docker compose up --build
```

The first run takes a few minutes while it assembles everything. You will see a lot
of text scroll by. That is normal. When it settles down and stops scrolling, it is
ready.

**Important:** the player and team names are real, but the numbers are made up. Do
not quote them as facts.

### Option B: Use real NBA data

Real data has to be downloaded once from the NBA's stats service. That download has
to happen from a normal home internet connection, because the NBA blocks requests
coming from data centers.

Run these two commands, one at a time, waiting for each to finish:

```bash
python3 -m venv .venv && ./.venv/bin/pip install -e .
./.venv/bin/python scripts/ingest.py
```

The first sets up the tools, the second downloads four seasons of NBA statistics. The
download takes a couple of minutes and prints a running list of what it collected.

Then start the app:

```bash
docker compose up --build
```

You only ever have to do the download once. To refresh with newer games later, run the
`ingest.py` line again.

### Open the website

With either option running, open your web browser and go to:

**http://localhost:8080**

You should see the CourtVision AI dashboard. Leave the Terminal window open while you
use the site. Closing it stops the app.

---

## A tour of the site

There are five pages, listed across the top of the screen.

### League

**Answers:** who is actually good, and why?

The big chart plots every team by how well it scores and how well it defends.

- Left to right: **offense**. Further right means the team scores more efficiently.
- Top to bottom: **defense**. Further down means the team defends better. (The axis
  is flipped on purpose so that the good direction is down, which makes the
  bottom-right corner the best place to be.)

So the teams in the **bottom-right corner are the best teams**, strong at both ends.
Top-left is the worst. Hover over any dot to see the exact numbers.

Below the chart is the full standings table: wins, losses, and the efficiency numbers
for every team. Use the season dropdown in the top right to look at earlier seasons.

### Players

**Answers:** how good is this player, and who plays like them?

You can either type a name in the search box or scroll the alphabetical list of every
player from the current season. Accents do not matter, so typing "jokic" finds
"Jokić".

Click any player and you will see:

- **Headline numbers** for their most recent season: points, rebounds, assists,
  shooting efficiency, and how much of the offense runs through them.
- **A career chart** showing how their points, rebounds, and assists have changed
  season to season.
- **An AI scouting report** button. Press it and the assistant writes a written
  evaluation of the player, in the style of a scout's notes. It is built only from
  the statistics on that page, so it cannot invent things it has heard elsewhere.
  (This needs an AI key. See [Turning on the AI features](#turning-on-the-ai-features).)
- **Similar players**, found by a machine learning model that compares 15 different
  aspects of how a player plays. This is matching on *style*, not on quality, so a
  role player can be similar to a star if they do the same things in the same
  proportions.

To get back to the full player list, press the "All players" button next to the
search box.

### Leaderboards

**Answers:** who leads the league in this?

Pick a statistic and a season from the two dropdowns, and you get the top players as a
ranked bar chart with exact values. Available statistics include the familiar ones
(points, rebounds, assists per game) and the analytical ones explained in the
[Glossary](#glossary-what-the-statistics-mean).

Only players with at least 40 games are included, which keeps out players who had a
few unusually good nights in limited action.

### Predict

**Answers:** if these two teams played tonight, who would win?

Pick a home team and an away team. The bar shows each team's chance of winning, and
underneath you see the current form of both teams: their record over the last ten
games, their average margin of victory, and their record for the season.

**How much should you trust it?** The model was tested on an entire NBA season it had
never seen before, and it called about **two out of three games correctly**.
Professional betting operations land around seven out of ten, so this is respectable
but not magic.

**What it does not know:** who is injured, who is resting, or who was traded this
week. It reads a team's recent results, not its roster. A team missing its best
player will look better on paper here than it should. Treat the number as a starting
point, not a verdict.

### Ask

**Answers:** anything you can put into words.

Type a basketball question in plain English and press Ask. For example:

- "Which team improved its defense the most this season?"
- "Compare Luka Doncic and Nikola Jokic"
- "Who are the most efficient high volume scorers?"
- "Which teams are best on the road?"

The assistant translates your question into database queries, runs them, reads the
results, and writes an answer using only the numbers it found. It takes a few seconds
because it often runs several queries in a row.

**The most important part** is underneath the answer: a section called "How this
answer was produced". Open it and you see every single query the assistant ran and the
data that came back. This means you can always check its work. If an answer looks
surprising, look at the queries. Most AI tools ask you to trust them, and this one
shows you receipts instead.

If the data cannot answer your question, it will say so rather than guessing. It only
knows the four NBA seasons in the database. It does not know about news, injuries,
contracts, or anything outside those statistics.

---

## Turning on the AI features

The Ask page and the scouting reports need a key from an AI provider. The other four
pages work without one.

1. **Get a key.** The simplest free option is Google Gemini. Go to
   [aistudio.google.com/apikey](https://aistudio.google.com/apikey), sign in, and
   create a key. Copy it. (Anthropic and OpenAI also work if you prefer those.)

2. **Put the key in the settings file.** In the project folder there is a file called
   `.env.example`. Make a copy of it named `.env`, which you can do in the Terminal:

   ```bash
   cp .env.example .env
   ```

   Open `.env` in any text editor. Find the line that reads `GEMINI_API_KEY=` and
   paste your key right after the equals sign, with no spaces or quotes:

   ```
   GEMINI_API_KEY=AIzaSyC-your-actual-key-here
   ```

   Save the file.

3. **Restart the app.** In the Terminal window running the app, press `Control` and
   `C` together to stop it, then start it again with `docker compose up`.

Your key stays on your computer. The `.env` file is deliberately excluded from the
project's version history, so it can never be uploaded to the internet by accident.

**One thing to know about cost:** AI providers charge for usage beyond their free
tier. Typical questions cost a fraction of a cent, but the meter is running on their
side, not ours. The free Gemini tier is generous enough for normal exploration.

---

## Stopping the app

In the Terminal window where it is running, press `Control` and `C` together.

If you want to be thorough and shut down the background pieces too:

```bash
docker compose down
```

Your data is not deleted. Starting it again is just `docker compose up`.

---

## If something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| The browser says the site cannot be reached | The app is not running yet, or is still starting | Check the Terminal. If text is still scrolling, wait. If it stopped with an error, read the row below that matches it. |
| A message about "no warehouse" | There is no NBA data yet | Either use demo mode (`COURTVISION_DEMO=1 docker compose up`) or run the download step from Option B. |
| "Cannot connect to the Docker daemon" | Docker Desktop is not running | Open Docker Desktop, wait for the whale icon to settle, then try again. |
| The Ask page says AI is not configured | No AI key found | Follow [Turning on the AI features](#turning-on-the-ai-features), then restart the app. |
| "port is already allocated" | Something else on your computer is using that port | Stop the other program, or stop any older copy of this app with `docker compose down`. |
| Numbers look wrong or out of date | The data is a snapshot from when you downloaded it | Run the `ingest.py` download step again to refresh. |
| The download step fails or times out | The NBA's stats service is rate limiting you | Wait a few minutes and run it again. Do not use a VPN, since those are often blocked. |

---

## Glossary: what the statistics mean

The dashboard uses the vocabulary of modern basketball analysis. Here is what each
term means in plain language.

**Per game.** Most numbers are shown per game rather than as season totals, so
players who missed games can be compared fairly. "24.5 points per game" means that is
their average in the games they played.

**Offensive rating.** Points a team scores per 100 possessions. Using possessions
instead of games removes the effect of a fast or slow style, so a fast team is not
credited just for playing more possessions. Around 115 is average; above 120 is
excellent.

**Defensive rating.** Points a team allows per 100 possessions. **Lower is better.**
Around 115 is average; below 110 is excellent.

**Net rating.** Offensive rating minus defensive rating. The single best one-number
summary of team quality. Positive means the team outscores opponents; a net rating
above +8 usually indicates a championship contender.

**Pace.** How many possessions a team uses per game. High pace means a fast,
run-and-gun style; low pace means a deliberate, half-court style. Neither is better,
it is a style choice.

**True shooting percentage (TS%).** The best single measure of scoring efficiency. It
counts two pointers, three pointers, and free throws together and weights them by what
they are actually worth. League average is about 57 percent; above 60 percent is very
efficient.

**Effective field goal percentage (eFG%).** Like regular shooting percentage, but it
gives proper credit for three pointers being worth more than two pointers. It ignores
free throws, which is the main difference from true shooting.

**Usage rate.** The share of the team's offensive possessions a player finishes while
on the floor, by shooting, drawing a foul, or turning the ball over. Around 20 percent
is an average role; above 30 percent means the offense runs through that player.

**Assist percentage.** The share of teammates' baskets a player assisted while on the
floor. A measure of playmaking responsibility.

**Rebound percentage.** The share of available rebounds a player grabbed while on the
floor. Fairer than raw rebound counts, because it accounts for how many rebounds were
even available.

**PIE (Player Impact Estimate).** The NBA's own attempt at a single all-in-one rating,
estimating a player's share of everything positive that happened in their games.
Useful for a quick read, but no single number captures basketball fully.

**Win probability.** For a given matchup, the estimated chance the home team wins. 50
percent means a coin flip. Home teams win about 55 percent of NBA games overall, so
anything above that is a real edge for the home side.

---

## Where to go next

- The [main README](../README.md) has the technical setup, the full list of features,
  and the project architecture.
- [`docs/PROJECT_REPORT.md`](PROJECT_REPORT.md) documents every decision made while
  building this, including the experiments that did not work.
- [`notebooks/model_evaluation.ipynb`](../notebooks/model_evaluation.ipynb) shows the
  evidence behind the prediction and similarity models, with charts.
