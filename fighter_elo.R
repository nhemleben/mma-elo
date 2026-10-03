parse_date <- function(date_string) {
  date_formats <- c("%B %d, %Y", "%B %d %Y", "%d %B, %Y", "%d %B %Y")

  for (date_format in date_formats) {
    date_obj <- as.Date(date_string, format=date_format)
    if (!is.na(date_obj)) {
      return(date_obj)
    }
  }
  return(as.Date(NA))
}

args <- commandArgs(trailingOnly=TRUE)
if (length(args) < 1 || length(args) > 2) {
  stop('Usage: Rscript fighter_elo.R "Fighter Name" [output.png]')
}

requested_name <- args[1]
output_file <- if (length(args) == 2) {
  args[2]
} else {
  safe_name <- gsub("[^A-Za-z0-9]+", "_", requested_name)
  paste0("fighter_elo_", tolower(safe_name), ".png")
}

scraped_results <- read.csv2("results.csv", stringsAsFactors=FALSE)
extra_results <- read.csv2("results_extra.csv", stringsAsFactors=FALSE)
results <- rbind(scraped_results, extra_results)
results$Date <- as.Date(vapply(results$Date, parse_date, as.Date(NA)))
results <- results[order(results$Date, results$Fight.Number), ]

all_names <- unique(c(as.character(results$Fighter), as.character(results$Opponent)))
matches <- all_names[tolower(all_names) == tolower(requested_name)]
if (length(matches) == 0) {
  suggestions <- agrep(requested_name, all_names, ignore.case=TRUE, value=TRUE)
  if (length(suggestions) > 0) {
    stop(paste("Fighter not found. Similar names:", paste(head(suggestions, 10), collapse="; ")))
  }
  stop(paste("Fighter not found:", requested_name))
}
fighter_name <- matches[1]

scores <- setNames(rep(1000, length(all_names)), all_names)
career_dates <- as.Date(character())
career_scores <- numeric()
starting_date <- min(results$Date[results$Fighter == fighter_name |
                                  results$Opponent == fighter_name], na.rm=TRUE)
career_dates <- c(career_dates, starting_date - 1)
career_scores <- c(career_scores, scores[fighter_name])

for (i in seq_len(nrow(results))) {
  fight <- results[i, ]
  fighter <- as.character(fight$Fighter)
  opponent <- as.character(fight$Opponent)
  result <- as.character(fight$Result)

  if (result == "def." || result == "def") {
    fighter_result <- 1
    opponent_result <- 0
  } else if (result == "vs." || result == "vs") {
    fighter_result <- 0.5
    opponent_result <- 0.5
  } else {
    next
  }

  fighter_expected <- 1 / (1 + 10 ^ ((scores[opponent] - scores[fighter]) / 400))
  opponent_expected <- 1 - fighter_expected
  scores[fighter] <- round(scores[fighter] + 32 * (fighter_result - fighter_expected))
  scores[opponent] <- round(scores[opponent] + 32 * (opponent_result - opponent_expected))

  if (fighter == fighter_name || opponent == fighter_name) {
    career_dates <- c(career_dates, as.Date(fight$Date))
    career_scores <- c(career_scores, scores[fighter_name])
  }
}

png(output_file, width=1200, height=700, res=120)
plot(career_dates, career_scores, type="s", lwd=2, col="#176B62",
     xlab="Fight date", ylab="Elo rating", main=paste(fighter_name, "Elo across career"),
     ylim=range(c(career_scores, 1000)))
abline(h=1000, col="gray60", lty=2)
dev.off()

cat("Career fights:", length(career_scores) - 1, "\n")
cat("Final Elo:", tail(career_scores, 1), "\n")
cat("Chart saved to:", output_file, "\n")