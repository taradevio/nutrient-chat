from fastapi import FastAPI
from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, Literal
import uvicorn

app = FastAPI(title="Nutrition Middleware")

#Schema

class BahanMentah(BaseModel):
    nama: str
    urt: Optional[str] = None
    tipe: Literal["main", "oil", "other"]


class BahanRow(BaseModel):
    nama_masakan: str
    urt_masakan: str
    estimasi_gram: float
    faktor_matang_mentah: float
    persen_minyak_terserap: Optional[float] = None
    keterangan: Optional[str] = None
    bahan_mentah: list[BahanMentah]

    @field_validator("estimasi_gram")
    @classmethod
    def estimasi_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError(f"estimasi_gram harus > 0, dapat: {v}")
        return v

    @field_validator("faktor_matang_mentah")
    @classmethod
    def faktor_must_be_reasonable(cls, v):
        if not (0.1 <= v <= 5.0):
            raise ValueError(f"faktor_matang_mentah tidak wajar: {v}. Harap klarifikasi.")
        return v

    @field_validator("persen_minyak_terserap")
    @classmethod
    def persen_must_be_valid(cls, v):
        if v is not None and not (0 <= v <= 100):
            raise ValueError(f"persen_minyak_terserap tidak valid: {v}. Harap klarifikasi.")
        return v

    @model_validator(mode="after")
    def validate_oil_needs_persen(self):
        has_oil = any(b.tipe == "oil" for b in self.bahan_mentah)
        if has_oil and self.persen_minyak_terserap is None:
            raise ValueError(
                f"Masakan '{self.nama_masakan}' punya bahan oil "
                f"tapi persen_minyak_terserap tidak ada. Harap klarifikasi."
            )
        return self

    @model_validator(mode="after")
    def validate_one_main(self):
        main_count = sum(1 for b in self.bahan_mentah if b.tipe == "main")
        if main_count != 1:
            raise ValueError(
                f"Masakan '{self.nama_masakan}' harus punya tepat 1 bahan "
                f"tipe 'main', dapat: {main_count}"
            )
        return self


class CalcRequest(BaseModel):
    waktu_makan: str
    rows: list[BahanRow]


#Result Schema

class BahanMentahResult(BaseModel):
    nama: str
    urt: Optional[str] = None
    tipe: str
    berat_mentah_gr: Optional[float] = None  # null untuk tipe other


class BahanRowResult(BaseModel):
    nama_masakan: str
    urt_masakan: str
    estimasi_gram: float
    matang_mentah_gr: float
    minyak_terserap_gr: float
    keterangan: Optional[str] = None
    bahan_mentah: list[BahanMentahResult]


class CalcResponse(BaseModel):
    waktu_makan: str
    rows: list[BahanRowResult]


# Calculation Logic

def calculate_row(row: BahanRow) -> BahanRowResult:
    matang_mentah_gr = round(row.faktor_matang_mentah * row.estimasi_gram, 1)
    minyak_terserap_gr = round(
        (row.persen_minyak_terserap / 100) * row.estimasi_gram, 1
    ) if row.persen_minyak_terserap else 0.0

    bahan_results = []
    for bahan in row.bahan_mentah:
        if bahan.tipe == "main":
            berat = matang_mentah_gr
        elif bahan.tipe == "oil":
            berat = minyak_terserap_gr
        else:  # other — tidak ada berat
            berat = None

        bahan_results.append(BahanMentahResult(
            nama=bahan.nama,
            urt=bahan.urt,
            tipe=bahan.tipe,
            berat_mentah_gr=berat
        ))

    return BahanRowResult(
        nama_masakan=row.nama_masakan,
        urt_masakan=row.urt_masakan,
        estimasi_gram=row.estimasi_gram,
        matang_mentah_gr=matang_mentah_gr,
        minyak_terserap_gr=minyak_terserap_gr,
        keterangan=row.keterangan,
        bahan_mentah=bahan_results
    )


# Endpoint

@app.post("/calculate", response_model=CalcResponse)
async def calculate(payload: CalcRequest):
    return CalcResponse(
        waktu_makan=payload.waktu_makan,
        rows=[calculate_row(row) for row in payload.rows]
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
