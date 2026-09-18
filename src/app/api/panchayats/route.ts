import { NextResponse } from "next/server";
import { PANCHAYATS, BLOCK } from "@/lib/panchayats";
import { getBlockForecast, correctForGP } from "@/lib/downscale";

export async function GET() {
  const block = getBlockForecast();
  const panchayats = PANCHAYATS.map((gp) => ({
    ...gp,
    corrected: correctForGP(gp, block),
  }));

  return NextResponse.json({
    block: { name: BLOCK.name, forecast: block, referenceElevationM: BLOCK.elevationM },
    panchayats,
  });
}
