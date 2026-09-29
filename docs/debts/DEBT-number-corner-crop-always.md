## DEBT-number-corner-crop-always — the number-corner crop is sent only on a retry

**Gap.** `geometry/crop.py` upscales the collector number to at least 600px, but the batch script uses it only after a weak first read. T1 misses (`051/197` for `031/197`, `271/167` for `211/167`) are confident reads with the name right and the digits wrong, so no confidence threshold fires on them.

**Experiment.** Attach the crop beside the downscaled card on every card and A/B it on T1. Cost is about double the image tokens on a job that costs $5 to $15 per 10k cards. It may do nothing: nobody has measured whether enlarging the number helps by itself.
