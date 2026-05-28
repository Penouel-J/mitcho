SELECT
  SQLDATE,
  DATE,
  Year,
  MonthYear,

  -- Acteurs
  Actor1Name,
  Actor1CountryCode,
  Actor1Type1Code,

  Actor2Name,
  Actor2CountryCode,
  Actor2Type1Code,

  -- Evénements
  EventCode,
  EventBaseCode,
  EventRootCode,
  QuadClass,
  GoldsteinScale,

  -- Intensité médiatique
  NumMentions,
  NumSources,
  NumArticles,
  AvgTone,

  -- Géographie
  ActionGeo_FullName,
  ActionGeo_CountryCode,
  ActionGeo_ADM1Code,
  ActionGeo_Lat,
  ActionGeo_Long,

  -- Source
  SOURCEURL

FROM
  `gdelt-bq.gdeltv2.events`

WHERE

  -- Zone d'étude
  ActionGeo_CountryCode IN ('BN', 'TO', 'NI', 'NG')

  -- Période
  AND Year BETWEEN 2020 AND 2026

  -- Acteurs clés
  AND (
    Actor1Type1Code IN ('AGR','BUS','CVL','GOV','IGO','LAB')
    OR
    Actor2Type1Code IN ('AGR','BUS','CVL','GOV','IGO','LAB')
  )

  -- Evénements importants
  AND (

    -- =========================================
    -- 1. LOGISTIQUE / FRONTIÈRES / BLOCAGES
    -- =========================================
    EventCode IN (
      '163',   -- embargo / sanctions
      '191',   -- blocus
      '144',   -- barrages routiers
      '085',   -- levée sanctions
      '1312',  -- menace embargo
      '1381'   -- menace blocus
    )

    OR

    -- =========================================
    -- 2. ECONOMIE / COOPERATION / INFLATION
    -- =========================================
    EventCode IN (
      '0211',
      '0311',
      '061',
      '1011',
      '1211',
      '1621'
    )

    OR

 
    -- 3. VIE CHÈRE / MANIFESTATIONS

    EventCode IN (
      '141',
      '1412',
      '143',
      '1432',
      '145',
      '1043'
    )

    OR


    -- 4. AIDE HUMANITAIRE / PÉNURIES
  
    EventCode IN (
      '0233',
      '0333',
      '073',
      '1033',
      '1223',
      '0863'
    )

    OR

    -- 5. SIGNAUX FAIBLES / SENTIMENT
  
    EventCode IN (
      '012',
      '013',
      '014',
      '111',
      '114',
      '1311'
    )
  )

ORDER BY
  SQLDATE ASC