// Minimal stub so the sketch can be syntax-checked on a PC (g++ -fsyntax-only). Not a simulator.
#pragma once
#include <stdint.h>
#include <algorithm>
#define BLACK 0
#define WHITE 1
#define GREEN 2
#define RED 3
#define YELLOW 4
#define DARKGREEN 5
#define MAROON 6
#define ADC_11db 3
#define pdTRUE 1
typedef uint32_t TickType_t; typedef void* QueueHandle_t;
struct Btn { bool wasPressed(); };
struct LcdT { void fillScreen(int); void setTextColor(int,int); void setTextSize(int); void drawString(const char*,int,int); void drawNumber(long,int,int); void drawFloat(float,int,int,int); void fillRect(int,int,int,int,int); void drawRect(int,int,int,int,int); void drawFastVLine(int,int,int,int); };
struct AxpT { void SetLDOEnable(int,bool); };
struct M5Stub { Btn BtnA,BtnB,BtnC; LcdT Lcd; AxpT Axp; void begin(); void update(); };
extern M5Stub M5; struct SerialStub { void begin(long); }; extern SerialStub Serial;
uint32_t millis(); void delay(uint32_t); float analogReadMilliVolts(int); void analogSetPinAttenuation(int,int);
TickType_t xTaskGetTickCount(); void vTaskDelayUntil(TickType_t*,int);
QueueHandle_t xQueueCreate(int,int); int xQueueSend(QueueHandle_t,const void*,int); int xQueueReceive(QueueHandle_t,void*,int);
int xTaskCreatePinnedToCore(void(*)(void*),const char*,int,void*,int,void*,int);
template<class T> T constrain(T v,T a,T b){return v<a?a:(v>b?b:v);}
