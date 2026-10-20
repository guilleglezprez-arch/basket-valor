"""Prueba si GitHub puede descargar estadísticas avanzadas de la NBA (stats.nba.com)."""
import sys
from nba_api.stats.endpoints import leaguedashteamstats, leagueseasonmatchups
ok = 0
try:
    df = leaguedashteamstats.LeagueDashTeamStats(measure_type_detailed_defense="Opponent", per_mode_detailed="PerGame", season="2025-26", timeout=40).get_data_frames()[0]
    print("PRUEBA 1 OK: estadísticas de lo que permite cada equipo.", df.shape)
    print([c for c in df.columns if "OPP_FG3" in c or "OPP_REB" in c][:8]); ok += 1
except Exception as e:
    print("PRUEBA 1 FALLÓ:", repr(e))
try:
    df = leagueseasonmatchups.LeagueSeasonMatchups(season="2025-26", off_player_id_nullable=1628973, def_player_id_nullable=1628401, timeout=40).get_data_frames()[0]
    print("PRUEBA 2 OK: emparejamientos Brunson vs Derrick White.", df.shape)
    print(df.head(3).to_string()); ok += 1
except Exception as e:
    print("PRUEBA 2 FALLÓ:", repr(e))
print(f"Resultado: {ok} de 2 pruebas correctas")
sys.exit(0 if ok else 1)
