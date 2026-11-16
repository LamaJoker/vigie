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

-- Un incident = une panne d'un site, de son début à son rétablissement.
CREATE TABLE IF NOT EXISTS incidents (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom           TEXT        NOT NULL,
    url           TEXT        NOT NULL,
    debut         TIMESTAMPTZ NOT NULL,
    fin           TIMESTAMPTZ CHECK (fin IS NULL OR fin >= debut),  -- NULL : panne en cours
    cause         TEXT,
    alerte_debut  BOOLEAN     NOT NULL DEFAULT false,  -- alerte de panne envoyée ?
    alerte_fin    BOOLEAN     NOT NULL DEFAULT false   -- alerte de rétablissement envoyée ?
);

-- Au plus UN incident ouvert par site : c'est la base elle-même qui garantit
-- qu'une panne ne déclenche qu'une seule alerte.
CREATE UNIQUE INDEX IF NOT EXISTS incidents_un_seul_ouvert ON incidents (url) WHERE fin IS NULL;
CREATE INDEX IF NOT EXISTS incidents_debut ON incidents (debut DESC);

-- Ajouté au lot 8.1. Pourquoi un incident s'est fermé quand ce n'est pas le retour du
-- site, par exemple « site retiré de la surveillance ». ADD COLUMN IF NOT EXISTS met
-- aussi à niveau les bases créées avant (les vraies migrations arrivent au lot 8.3).
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS motif_fin TEXT;
