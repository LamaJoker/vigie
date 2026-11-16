-- Lot 8.3 : la purge quotidienne cherche les mesures plus vieilles que la rétention,
-- tous sites confondus. Sans cet index, elle relirait toute la table à chaque fois.

CREATE INDEX sondes_date ON sondes (date);
