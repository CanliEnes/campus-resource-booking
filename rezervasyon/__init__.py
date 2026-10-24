"""Kampüs Kaynak Rezervasyon Sistemi - arayüzden bağımsız rezervasyon modülü."""

from .cekirdek import (
    KOMUT_ALANLARI,
    RezervasyonSistemi,
    gun_coz,
    zaman_coz,
    zaman_yaz,
)

__all__ = ["KOMUT_ALANLARI", "RezervasyonSistemi", "gun_coz", "zaman_coz", "zaman_yaz"]
