# Databricks notebook source
# MAGIC %md
# MAGIC # Harmful-domain feeds
# MAGIC - `mode=replay`: empties the tables and reloads the snapshots committed in `snapshots/`.
# MAGIC - `mode=live`: downloads the four feeds into the Volume as a new snapshot and loads it.
# MAGIC
# MAGIC Run the next cell first to show the parameters at the top, pick them, then Run all.

# COMMAND ----------

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.dropdown("mode", "replay", ["replay", "live"])
dbutils.widgets.text("domain", "a.b.doubleclick.net")  # used by the lookup cell

# COMMAND ----------

# MAGIC %pip install ..

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

from pathlib import Path

from threat_feeds import pipeline
from threat_feeds.checks import IS_LATEST_SNAPSHOT, check_latest_snapshot, domain_changes, reconciliation_counts
from threat_feeds.domains import lookup_domain
from threat_feeds.settings import Settings

settings = Settings(
    catalog=dbutils.widgets.get("catalog"),
    mode=dbutils.widgets.get("mode"),
    snapshots_dir=Path.cwd().parent / "snapshots",
)
pipeline.run(spark, settings)

# COMMAND ----------

# MAGIC %md ## Files in the latest snapshot

# COMMAND ----------

display(spark.table("feed_file_checks").where(IS_LATEST_SNAPSHOT).orderBy("feed"))

# COMMAND ----------

# MAGIC %md ## Listings vs `domain_current`

# COMMAND ----------

display(spark.createDataFrame([reconciliation_counts(spark)]))

# COMMAND ----------

# MAGIC %md ## Changes since the previous snapshot

# COMMAND ----------

display(domain_changes(spark))

# COMMAND ----------

# MAGIC %md ## `domain_current`

# COMMAND ----------

display(spark.table("domain_current").orderBy("domain"))

# COMMAND ----------

# MAGIC %md ## Lookup for the `domain` widget

# COMMAND ----------

answer = lookup_domain(spark, dbutils.widgets.get("domain"))
display(spark.createDataFrame([answer]))

# COMMAND ----------

# MAGIC %md ## Fail the run if a check failed

# COMMAND ----------

check_latest_snapshot(spark)
