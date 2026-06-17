CREATE TABLE IF NOT EXISTS informativos (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tipo text NOT NULL CHECK (tipo IN ('evento', 'publicacao', 'data_importante', 'imersao', 'workshop')),
  titulo text NOT NULL,
  descricao text,
  url text,
  data_evento date,
  data_fim date,
  ativo boolean DEFAULT true,
  destaque boolean DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_informativos_ativo ON informativos(ativo);
CREATE INDEX IF NOT EXISTS idx_informativos_tipo ON informativos(tipo);
CREATE INDEX IF NOT EXISTS idx_informativos_destaque ON informativos(destaque);
CREATE INDEX IF NOT EXISTS idx_informativos_data ON informativos(data_evento);
