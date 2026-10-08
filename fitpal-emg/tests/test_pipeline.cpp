// Host test: runs the same emg_dsp.h that is built into the firmware over a CSV of samples.
// usage: test_pipeline in.csv out_env.csv rest_t0 rest_t1 mvc_t0 mvc_t1 target
// in.csv columns: t_ms,mv   ->   out_env.csv: t_ms,env,act ; reps printed as "REP,start,dur,peak,mean,eff"
#include <cstdio>
#include <cstdlib>
#include "../firmware/fitpal_core2/emg_dsp.h"
int main(int argc, char **argv) {
  if (argc < 8) { fprintf(stderr, "bad args\n"); return 2; }
  FILE *in = fopen(argv[1], "r"), *out = fopen(argv[2], "w");
  if (!in || !out) return 2;
  const uint32_t r0 = atoi(argv[3]), r1 = atoi(argv[4]), m0 = atoi(argv[5]), m1 = atoi(argv[6]);
  fitpal::Pipeline p; fitpal::PipelineConfig pc; pc.mains_hz = 50.0f; p.begin(pc);
  p.det.cfg.target = atof(argv[7]);
  char line[128]; if (!fgets(line, sizeof line, in)) return 2;  // header
  unsigned t; float mv; fitpal::Rep rep; bool ok_rest = false;
  bool in_rest = false, in_mvc = false, cal_ok = false;
  fprintf(out, "t_ms,env,act\n");
  while (fscanf(in, "%u,%f", &t, &mv) == 2) {
    if (t == r0) { p.startRestCapture(); in_rest = true; }
    if (t == r1 && in_rest) { p.finishCapture(); in_rest = false; ok_rest = true; }
    if (t == m0) { p.startMvcCapture(); in_mvc = true; }
    if (t == m1 && in_mvc) { cal_ok = p.finishCapture(); in_mvc = false; }
    if (p.push(t, mv, rep))
      printf("REP,%u,%u,%.3f,%.3f,%d\n", rep.start_ms, rep.dur_ms, rep.peak, rep.mean, rep.effective ? 1 : 0);
    if (t % 5 == 0) fprintf(out, "%u,%.2f,%.4f\n", t, p.env, p.act);
  }
  printf("CAL,%d,%d,%.2f,%.2f\n", ok_rest, cal_ok, p.rest, p.mvc);
  return 0;
}
