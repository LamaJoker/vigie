-- Schéma de la base de Vigie. Peut être rejoué sans risque (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS sondes (
    id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date      TIMESTAMPTZ NOT NULL,
    nom       TEXT        NOT NULL,
    url       TEXT        NOT NULL,
    etat      TEXT        NOT NULL CHECK (etat IN ('UP', 'DOWN')),
    code      INTEGER     CHECK (code BETWEEN 100 AND 599),
    duree_ms  INTEGER     NOT NULL CHECK (duree_ms >= 0),
    erreur    TEXT
);

-- Accélère les deux questions les plus fréquentes :
-- « dernier résultat d'un site » et « résultats d'un site sur une période ».
CREATE INDEX IF NOT EXISTS sondes_url_date ON sondes (url, date DESC);
