import QtQuick
import QtQuick.Controls

Window {
    id: root
    visible: true
    visibility: Window.FullScreen
    color: "#101418"

    Rectangle {
        anchors.fill: parent
        color: "#101418"

        Column {
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.72, 720)
            spacing: 28

            Text {
                width: parent.width
                text: progressModel.stage === "failed" ? "Update Failed"
                    : progressModel.stage === "success" ? "Update Complete"
                    : "System Update"
                color: "#F4F7FA"
                font.pixelSize: 34
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            Text {
                width: parent.width
                text: progressModel.error.length > 0 ? progressModel.error : progressModel.message
                color: progressModel.stage === "failed" ? "#FF6B6B" : "#B8C2CC"
                font.pixelSize: 22
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
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
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
}
