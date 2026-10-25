-- Cria o banco e a tabela do Market Insights BR.
-- Execute no SSMS (ou outra ferramenta) conectado ao seu SQL Server.

IF DB_ID('MarketInsightsBR') IS NULL
    CREATE DATABASE MarketInsightsBR;
GO

USE MarketInsightsBR;
GO

IF OBJECT_ID('dbo.indicadores', 'U') IS NULL
CREATE TABLE dbo.indicadores (
    id               INT IDENTITY(1,1) NOT NULL,
    codigo           VARCHAR(30)       NOT NULL,
    data_referencia  DATE              NOT NULL,
    valor            DECIMAL(18,6)     NOT NULL,
    unidade          VARCHAR(30)       NOT NULL,
    fonte            VARCHAR(50)       NOT NULL,
    coletado_em      DATETIME2(0)      NOT NULL
        CONSTRAINT DF_indicadores_coletado_em DEFAULT SYSDATETIME(),

    CONSTRAINT PK_indicadores PRIMARY KEY (id),
    CONSTRAINT UQ_indicadores_codigo_data UNIQUE (codigo, data_referencia)
);
GO