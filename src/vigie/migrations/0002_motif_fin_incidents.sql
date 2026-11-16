-- Lot 8.1 : pourquoi un incident s'est fermé quand ce n'est pas le retour du site,
-- par exemple « site retiré de la surveillance ».
--
-- IF NOT EXISTS : les bases créées par le schema.sql des lots 8.1 et 8.2 ont déjà
-- cette colonne (voir 0001_initial.sql).

ALTER TABLE incidents ADD COLUMN IF NOT EXISTS motif_fin TEXT;
