SELECT DISTINCT ds.datasetid
FROM ndb.datasets AS ds
LEFT JOIN ndb.datasetdoi AS dsdoi ON dsdoi.datasetid = ds.datasetid
WHERE NOT ds.datasettypeid = 1
AND ds.datasetid = ANY(%s)
ORDER BY ds.datasetid;