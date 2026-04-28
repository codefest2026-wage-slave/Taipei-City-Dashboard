// Package app initiates the Gin server and connects to the postgreSQL database
/*
Developed By Taipei Urban Intelligence Center 2023-2024

// Lead Developer:  Igor Ho (Full Stack Engineer)
// Systems & Auth: Ann Shih (Systems Engineer)
// Data Pipelines:  Iima Yu (Data Scientist)
// Design and UX: Roy Lin (Prev. Consultant), Chu Chen (Researcher)
// Testing: Jack Huang (Data Scientist), Ian Huang (Data Analysis Intern)
*/
package app

import (
	"TaipeiCityDashboardBE/app/cache"
	"TaipeiCityDashboardBE/app/initial"
	"TaipeiCityDashboardBE/app/models"
	"TaipeiCityDashboardBE/app/routes"
	"TaipeiCityDashboardBE/global"
	"TaipeiCityDashboardBE/logs"

	"github.com/fvbock/endless"

	ort "github.com/yalue/onnxruntime_go"
)

// app.go is the main entry point for this application.
// initiates configures the postgreSQL, Redis, Gin router and starts the server.

// StartApplication initiates the main backend application, including the Gin router, postgreSQL, and Redis.
func StartApplication() {
	models.ConnectToDatabases("MANAGER", "DASHBOARD")
	defer models.CloseConnects("MANAGER", "DASHBOARD")

	cache.ConnectToRedis()
	defer cache.CloseConnect()

	initial.InitCronJobs()

	global.LMSession = models.InitLmSession()
	defer func() {
		global.LMSession.Destroy()
		ort.DestroyEnvironment()
	}()

	global.LMTokenizer = models.InitTokenizer()

	addr := global.GinAddr
	if err := endless.ListenAndServe(addr, routes.GetRouter()); err != nil {
		logs.Warn(err)
	}
	logs.FInfo("Server on %v stopped", addr)
}

func MigrateManagerSchema() {
	models.ConnectToDatabases("MANAGER")
	defer models.CloseConnects("MANAGER")

	models.MigrateManagerSchema()
	initial.InitDashboardManager()
}

func InsertDashbaordSampleData() {
	models.ConnectToDatabases("DASHBOARD")
	defer models.CloseConnects("DASHBOARD")
	initial.InitSampleCityData()
}
