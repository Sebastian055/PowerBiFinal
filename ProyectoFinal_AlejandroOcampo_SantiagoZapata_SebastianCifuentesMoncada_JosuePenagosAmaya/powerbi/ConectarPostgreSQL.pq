let
    Servidor = "localhost:5433",
    BaseDatos = "solar_db",
    Origen = PostgreSQL.Database(Servidor, BaseDatos),
    FactTelemetria = Origen{[Schema="public",Item="fact_telemetria_energia"]}[Data],
    FactEventos    = Origen{[Schema="public",Item="fact_eventos_operativos"]}[Data],
    DimInversor    = Origen{[Schema="public",Item="dim_inversor"]}[Data],
    DimFecha       = Origen{[Schema="public",Item="dim_fecha"]}[Data],
    DimFranja      = Origen{[Schema="public",Item="dim_franja_horaria"]}[Data],
    DimTipoEvento  = Origen{[Schema="public",Item="dim_tipo_evento"]}[Data],
    AuditCalidad   = Origen{[Schema="public",Item="audit_calidad_etl"]}[Data]
in
    [
        fact_telemetria_energia = FactTelemetria,
        fact_eventos_operativos = FactEventos,
        dim_inversor = DimInversor,
        dim_fecha = DimFecha,
        dim_franja_horaria = DimFranja,
        dim_tipo_evento = DimTipoEvento,
        audit_calidad_etl = AuditCalidad
    ]