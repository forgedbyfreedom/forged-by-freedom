#!/bin/bash
# setup_channels.sh — create all channel folders for transcript organization

channels=(
@BarbellMedicine @ChrisBumstead @DrGabrielleLyon @FoundMyFitness @HighLifeWorkout
@ISSAPersonalTrainer @JeffNippard @MulliganBrothers @NasmOrgPersonalTrainer
@NicksStrengthandPower @PeterAttiaMD @RenaissancePeriodization @RyanHumiston
@ThinkBIGBodybuilding @anabolicbodybuilding @anabolicuniversity @bodybuildingcom
@eliteftsofficial @hanyrambod_FST7 @realtattered @rxmuscle @sam_sulek
@theconditioncoaches @AndrewHuberman @HubermanLabClips @LayneNorton @EricHelms
@AlanAragon @ScienceforSport @BenGreenfieldFitness @MorePlatesMoreDates
@vigoroussteve @LeoAndLongevity @ThomasDeLauer @GregDoucette @TonyHuge
@DerekMPMD @JayCampbell @KennyKO @WestsideBarbell @JuggernautTrainingSystems
@KabukiStrength @MattWenning @MarkBell @SquatUniversity @HybridPerformanceMethod
@OmarIsuf @JockoPodcast @AndyFrisella @TimKennedy @BrianShawStrength
@MattBrownMMA @LexFridman @DavidGoggins @NickBareFitness @TacticalHypertrophy
@HardToKillFitness @ModernDaySniper @FouadAbiadMedia @FlexLewis @DennisJamesTV
@DorianYates @KingKamali @GuyCisternino @BenChowBodybuilding @JAYCUTLER @KaiGreene @BranchWarren
)

for c in "${channels[@]}"; do
  mkdir -p "$c"
  echo "This folder holds transcript text files for $c." > "$c/README.txt"
done

echo "✅ Created ${#channels[@]} channel folders successfully."
