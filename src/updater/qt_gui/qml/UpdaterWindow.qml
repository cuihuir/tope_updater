import QtQuick
import QtQuick.Controls

Window {
    id: root
    visible: true
    visibility: Window.FullScreen
    color: "#101418"

    Rectangle {
        anchors.centerIn: parent
        width: root.height
        height: root.width
        rotation: 90
        color: "#101418"

        Row {
            anchors.left: parent.left
            anchors.leftMargin: Math.max(24, parent.width * 0.035)
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - anchors.leftMargin - Math.max(24, parent.width * 0.035)
            height: Math.min(parent.height * 0.74, 326)
            spacing: Math.max(28, parent.width * 0.035)

            Image {
                id: logoColumn
                width: Math.min(parent.width * 0.26, 260)
                height: parent.height
                anchors.verticalCenter: parent.verticalCenter
                source: "../assets/tope-logo-en.svg"
                fillMode: Image.PreserveAspectFit
                smooth: true
                mipmap: true
            }

            Column {
                id: statusColumn
                width: parent.width - logoColumn.width - actionColumn.width - parent.spacing * 2
                anchors.verticalCenter: parent.verticalCenter
                spacing: 20

                Text {
                    width: parent.width
                    text: progressModel.stage === "failed" ? "Update Failed"
                        : progressModel.stage === "success" ? "Update Complete"
                        : "System Update"
                    color: "#F4F7FA"
                    font.pixelSize: 34
                    horizontalAlignment: Text.AlignLeft
                    wrapMode: Text.WordWrap
                }

                Text {
                    width: parent.width
                    text: progressModel.error.length > 0 ? progressModel.error : progressModel.message
                    color: progressModel.stage === "failed" ? "#FF6B6B" : "#B8C2CC"
                    font.pixelSize: 22
                    horizontalAlignment: Text.AlignLeft
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                }

                Rectangle {
                    width: parent.width
                    height: 18
                    radius: 6
                    color: "#2A3138"

                    Rectangle {
                        width: parent.width * progressModel.progress / 100
                        height: parent.height
                        radius: 6
                        color: progressModel.stage === "failed" ? "#FF6B6B" : "#47D18C"
                    }
                }

                Text {
                    width: parent.width
                    text: progressModel.progress + "%"
                    color: "#F4F7FA"
                    font.pixelSize: 28
                    horizontalAlignment: Text.AlignLeft
                }
            }

            Column {
                id: actionColumn
                width: Math.max(190, Math.min(parent.width * 0.20, 240))
                anchors.verticalCenter: parent.verticalCenter
                spacing: 18
                visible: progressModel.terminal

                Item {
                    width: parent.width
                    height: 1
                }

                Text {
                    width: parent.width
                    text: "Entering system in " + progressModel.countdownSeconds + "s"
                    color: "#B8C2CC"
                    font.pixelSize: 20
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    width: parent.width
                    height: 56
                    radius: 8
                    color: "#F4F7FA"

                    Text {
                        anchors.centerIn: parent
                        text: "Enter System"
                        color: "#101418"
                        font.pixelSize: 20
                        font.bold: true
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: progressModel.confirmExit()
                    }
                }
            }
        }
    }

    Timer {
        interval: 1000
        repeat: true
        running: progressModel.terminal && progressModel.countdownSeconds > 0
        onTriggered: progressModel.tickTerminalCountdown()
    }
}
