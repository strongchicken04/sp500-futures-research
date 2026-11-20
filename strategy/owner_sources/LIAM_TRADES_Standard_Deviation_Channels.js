const predef = require("./tools/predef");
const meta = require("./tools/meta");
const StdDev = require("./tools/StdDev");
const p = require("./tools/plotting");

class NOMLinearRegressionChannel {
    map(d, i) {
        const y = d.value();
        
        return {
            x: i,
            y: y
        }
    }
}

function lrcPlotter(canvas, indicatorInstance, history) {
    const periods = indicatorInstance.props.period;
    const band1StdDevs = indicatorInstance.props.band1StdDevs;
    const band2StdDevs = indicatorInstance.props.band2StdDevs;
	const band3StdDevs = indicatorInstance.props.band3StdDevs;
    const startIndex = Math.max(history.data.length - periods, 0);
    const endIndex = history.data.length - 1;
    
    if (periods < 2 || history.data.length < 2) {
        return;
    }
    
    // Get mean of X and Y and stdDev of Y
    const { xMean, yMean, stdDev } = calculateMeanAndStdDev(startIndex, endIndex, periods, history);
    
    // Calculate least squares linear regression
    const { b1, b0 } = linearRegression(startIndex, endIndex, history, xMean, yMean)
    
    // Calculate 2 points for the linear regression line
    const x1 = startIndex;
    const x2 = endIndex;
    const y1 = b1 * x1 + b0;
    const y2 = b1 * x2 + b0;
    
    // Convert x to date format for plotting
    const xDate1 = p.x.get(history.get(startIndex));
    const xDate2 = p.x.get(history.get(endIndex));

    // Work out how far (in x-axis units) one bar spans on average, so the
    // forward rays extend a consistent distance regardless of tick spacing,
    // then project a future x point that the rays will extend out to.
    const rayXDate = calculateRayXDate(xDate1, xDate2, startIndex, endIndex, indicatorInstance.props.rayBars);
    
    // Draw middle LR line
	if (indicatorInstance.props.linearRegressionLineEnabled) {
		const lrPath = p.createPath();
		lrPath.moveTo(xDate1, y1);
		lrPath.lineTo(xDate2, y2);
		canvas.drawPath(lrPath.end(), {
			color: indicatorInstance.props.linearRegression,
			width: indicatorInstance.props.linearRegressionWidth,
		});

		// Forward-extending horizontal ray from the right-hand end of the
		// regression line, held flat at the last regression value.
		if (indicatorInstance.props.rayExtensionEnabled) {
			const lrRayPath = p.createPath();
			lrRayPath.moveTo(xDate2, y2);
			lrRayPath.lineTo(rayXDate, y2);
			canvas.drawPath(lrRayPath.end(), {
				color: indicatorInstance.props.linearRegression,
				width: indicatorInstance.props.linearRegressionWidth,
			});
		}
	}
    
    // Draw first upper and lower bands
    if (indicatorInstance.props.band1Enabled) {
        const band1UpperY = y2 + band1StdDevs * stdDev;
        const band1LowerY = y2 - band1StdDevs * stdDev;

        const band1Upper = p.createPath();
        band1Upper.moveTo(xDate1, y1 + band1StdDevs * stdDev);
        band1Upper.lineTo(xDate2, band1UpperY);
        canvas.drawPath(band1Upper.end(), {
            color: indicatorInstance.props.band1Color,
            width: indicatorInstance.props.lineWidth1
        });
    
        const band1Lower = p.createPath();
        band1Lower.moveTo(xDate1, y1 - band1StdDevs * stdDev);
        band1Lower.lineTo(xDate2, band1LowerY);
        canvas.drawPath(band1Lower.end(), {
            color: indicatorInstance.props.band1Color,
            width: indicatorInstance.props.lineWidth1
        });

        // Forward-extending horizontal rays off the right-hand end of band 1
        if (indicatorInstance.props.rayExtensionEnabled) {
            const band1UpperRay = p.createPath();
            band1UpperRay.moveTo(xDate2, band1UpperY);
            band1UpperRay.lineTo(rayXDate, band1UpperY);
            canvas.drawPath(band1UpperRay.end(), {
                color: indicatorInstance.props.band1Color,
                width: indicatorInstance.props.lineWidth1
            });

            const band1LowerRay = p.createPath();
            band1LowerRay.moveTo(xDate2, band1LowerY);
            band1LowerRay.lineTo(rayXDate, band1LowerY);
            canvas.drawPath(band1LowerRay.end(), {
                color: indicatorInstance.props.band1Color,
                width: indicatorInstance.props.lineWidth1
            });
        }
    }
    
    // Draw second upper and lower bands
    if (indicatorInstance.props.band2Enabled) {
        const band2UpperY = y2 + band2StdDevs * stdDev;
        const band2LowerY = y2 - band2StdDevs * stdDev;

        const band2Upper = p.createPath();
        band2Upper.moveTo(xDate1, y1 + band2StdDevs * stdDev);
        band2Upper.lineTo(xDate2, band2UpperY);
        canvas.drawPath(band2Upper.end(), {
            color: indicatorInstance.props.band2Color,
            width: indicatorInstance.props.lineWidth2
        });
    
        const band1Lower = p.createPath();
        band1Lower.moveTo(xDate1, y1 - band2StdDevs * stdDev);
        band1Lower.lineTo(xDate2, band2LowerY);
        canvas.drawPath(band1Lower.end(), {
            color: indicatorInstance.props.band2Color,
            width: indicatorInstance.props.lineWidth2
        });

        // Forward-extending horizontal rays off the right-hand end of band 2
        if (indicatorInstance.props.rayExtensionEnabled) {
            const band2UpperRay = p.createPath();
            band2UpperRay.moveTo(xDate2, band2UpperY);
            band2UpperRay.lineTo(rayXDate, band2UpperY);
            canvas.drawPath(band2UpperRay.end(), {
                color: indicatorInstance.props.band2Color,
                width: indicatorInstance.props.lineWidth2
            });

            const band2LowerRay = p.createPath();
            band2LowerRay.moveTo(xDate2, band2LowerY);
            band2LowerRay.lineTo(rayXDate, band2LowerY);
            canvas.drawPath(band2LowerRay.end(), {
                color: indicatorInstance.props.band2Color,
                width: indicatorInstance.props.lineWidth2
            });
        }
    }
	
	// Draw third upper and lower bands
    if (indicatorInstance.props.band3Enabled) {
        const band3UpperY = y2 + band3StdDevs * stdDev;
        const band3LowerY = y2 - band3StdDevs * stdDev;

        const band3Upper = p.createPath();
        band3Upper.moveTo(xDate1, y1 + band3StdDevs * stdDev);
        band3Upper.lineTo(xDate2, band3UpperY);
        canvas.drawPath(band3Upper.end(), {
            color: indicatorInstance.props.band3Color,
            width: indicatorInstance.props.lineWidth3
        });
    
        const band1Lower = p.createPath();
        band1Lower.moveTo(xDate1, y1 - band3StdDevs * stdDev);
        band1Lower.lineTo(xDate2, band3LowerY);
        canvas.drawPath(band1Lower.end(), {
            color: indicatorInstance.props.band3Color,
            width: indicatorInstance.props.lineWidth3
        });

        // Forward-extending horizontal rays off the right-hand end of band 3
        if (indicatorInstance.props.rayExtensionEnabled) {
            const band3UpperRay = p.createPath();
            band3UpperRay.moveTo(xDate2, band3UpperY);
            band3UpperRay.lineTo(rayXDate, band3UpperY);
            canvas.drawPath(band3UpperRay.end(), {
                color: indicatorInstance.props.band3Color,
                width: indicatorInstance.props.lineWidth3
            });

            const band3LowerRay = p.createPath();
            band3LowerRay.moveTo(xDate2, band3LowerY);
            band3LowerRay.lineTo(rayXDate, band3LowerY);
            canvas.drawPath(band3LowerRay.end(), {
                color: indicatorInstance.props.band3Color,
                width: indicatorInstance.props.lineWidth3
            });
        }
    }
}

function calculateMeanAndStdDev(startIndex, endIndex, periods, history) {
    const stdDevTool = StdDev(periods);
    let xTotal = 0;
    let yTotal = 0;
    let stdDev = 0;
    
    for (let x = startIndex; x <= endIndex; x++) {
        let item = history.get(x);
        xTotal += x;
        yTotal += item.y;
        stdDev = stdDevTool(item.y);
    }
    
    return {
        xMean: xTotal / periods,
        yMean: yTotal / periods,
        stdDev: stdDev
    }
}

function linearRegression(startIndex, endIndex, history, xMean, yMean) {
    let num = 0;
    let den = 0;
    
    for (let x = startIndex; x <= endIndex; x++) {
        let item = history.get(x);
        num += (x - xMean) * (item.y - yMean);
        den += (x - xMean) * (x - xMean);
    }
    
    const b1 = num / den;
    return {
        b1: b1,
        b0: yMean - b1 * xMean
    }
}

// Works out an x-axis point some number of bars to the right of the last
// bar in the channel, so the rays extend a consistent distance forward
// regardless of how the x-axis values (dates/indices) are spaced on a tick
// chart. Handles x values that come back as Date objects or as plain
// numbers.
function calculateRayXDate(xDate1, xDate2, startIndex, endIndex, rayBars) {
    const totalBars = endIndex - startIndex;
    const isDate = xDate2 instanceof Date;
    const x1 = isDate ? xDate1.getTime() : xDate1;
    const x2 = isDate ? xDate2.getTime() : xDate2;

    const avgBarSpacing = totalBars > 0 ? (x2 - x1) / totalBars : 0;
    const futureX = x2 + avgBarSpacing * rayBars;

    return isDate ? new Date(futureX) : futureX;
}


module.exports = {
    name: "bnotb Standard Deviation Channels w Rays",
    description: "Standard Deviation Channels with Forward Rays",
    calculator: NOMLinearRegressionChannel,
    params: {
        period: predef.paramSpecs.period(100),
        linearRegression: predef.paramSpecs.color("#CFA600"),
		linearRegressionLineEnabled: predef.paramSpecs.bool(true),
		linearRegressionWidth: predef.paramSpecs.number(0.50, 0.01, 0.50),
		dividerForBand1Settings: predef.paramSpecs.enum({
            spacer: '——————————————————————————————————————————————————'
        }, 'spacer'),
        band1StdDevs: predef.paramSpecs.number(1, 0.001),
        band1Color: predef.paramSpecs.color("#B84BF2"),
        band1Enabled: predef.paramSpecs.bool(true),
		lineWidth1: predef.paramSpecs.number(1, 0.01, 0.50),
		dividerForBand2Settings: predef.paramSpecs.enum({
            spacer: '——————————————————————————————————————————————————'
        }, 'spacer'),
        band2StdDevs: predef.paramSpecs.number(2, 0.001),
        band2Color: predef.paramSpecs.color("#4894C7"),
        band2Enabled: predef.paramSpecs.bool(true),
		lineWidth2:predef.paramSpecs.number(1, 0.01, 0.50),
		dividerForBand3Settings: predef.paramSpecs.enum({
            spacer: '——————————————————————————————————————————————————'
        }, 'spacer'),
		band3StdDevs: predef.paramSpecs.number(3, 0.001),
		band3Color: predef.paramSpecs.color("#D0021B"),
		band3Enabled: predef.paramSpecs.bool(true),
        lineWidth3: predef.paramSpecs.number(1, 0.01, 0.50),
		dividerForRaySettings: predef.paramSpecs.enum({
            spacer: '——————————————————————————————————————————————————'
        }, 'spacer'),
        rayExtensionEnabled: predef.paramSpecs.bool(true),
        rayBars: predef.paramSpecs.number(50, 1),
    },
    tags: ["bnotb"],
    plotter: [
        predef.plotters.custom(lrcPlotter)
    ]
};
