SELECT DISTINCT ds.datasetid
FROM ndb.datasets AS ds
LEFT JOIN ndb.datasetdoi AS dsdoi ON dsdoi.datasetid = ds.datasetid
WHERE NOT ds.datasettypeid = 1
AND dsdoi.doi IS NULL
AND ds.recdatecreated > NOW() - INTERVAL %(interval)s
ORDER BY ds.datasetid;